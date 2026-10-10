"""Planning (§6.2.3): a template gives the skeleton DAG; the LLM may add,
remove or specialise steps for THIS project; the result is validated by
code before it's ever trusted (acyclic, every step has >=1 accept check,
every cap known or explicitly proposed, budgets within the project's
constraints) — a plan that fails validation never reaches the scheduler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from pokelab_brain.llm.jsonio import extract_json
from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.oak.intake import ProjectSpec

TEMPLATES_DIR = Path(__file__).parent / "templates"


class Budget(BaseModel):
    max_steps: int = 50
    max_tokens: int = 20_000
    max_gpu_s: float = 120.0


class PlanStep(BaseModel):
    id: str
    cap: str
    title: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    accept: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    after: list[str] = Field(default_factory=list)
    parallel_group: str | None = None


@dataclass
class ValidationError:
    reason: str


def load_template(kind: str) -> list[dict[str, Any]]:
    path = TEMPLATES_DIR / f"{kind}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no template for kind={kind!r}: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["steps"]


_ADAPT_PROMPT = """You adapt a research plan template for one specific project.

Project: {title} ({kind})
Goal: {goal}
Papers: {papers}
Known capability gaps that may need a new specialised step: {gaps}

Template steps (as JSON):
{template_steps}

You may add, remove, or specialise steps for this exact project. Every step
needs: id, cap, title, accept (at least one check string), after (dependency
step ids, acyclic). Reply with ONLY the adapted JSON array of steps (no
prose, no code fence) in the same shape as the template.
"""


def adapt_plan(
    project: ProjectSpec,
    template_steps: list[dict[str, Any]],
    gaps: list[str],
    router: LlmRouter,
    route: list[str],
    validation_feedback: str | None = None,
    **llm_kwargs,
) -> list[dict[str, Any]]:
    import json

    prompt = _ADAPT_PROMPT.format(
        title=project.title, kind=project.kind, goal=project.goal, papers=project.papers,
        gaps=gaps, template_steps=json.dumps(template_steps, indent=2),
    )
    if validation_feedback:
        prompt += (
            "\n\nYour previous attempt failed validation. Fix these exact problems, "
            f"using ONLY capability names from the known list given above:\n{validation_feedback}"
        )
    result = router.complete(messages=[{"role": "user", "content": prompt}], route=route, max_tokens=1500, **llm_kwargs)
    parsed = extract_json(result.content)
    if not isinstance(parsed, list):
        raise ValueError(f"plan adaptation did not return a JSON array: {result.content!r}")
    return parsed


def validate_plan(steps_raw: list[dict[str, Any]], known_caps: set[str], constraints: dict[str, Any]) -> tuple[list[PlanStep], list[ValidationError]]:
    errors: list[ValidationError] = []
    steps: list[PlanStep] = []

    for raw in steps_raw:
        try:
            step = PlanStep(**raw)
        except Exception as e:
            errors.append(ValidationError(f"step {raw.get('id', '?')!r} failed to parse: {e}"))
            continue
        if not step.accept:
            errors.append(ValidationError(f"step {step.id!r} has no accept checks"))
        if step.cap not in known_caps:
            errors.append(ValidationError(f"step {step.id!r} uses unknown capability {step.cap!r}"))
        max_gpu = constraints.get("max_gpu_minutes")
        if max_gpu is not None and step.budget.max_gpu_s > max_gpu * 60:
            errors.append(ValidationError(f"step {step.id!r} budget {step.budget.max_gpu_s}s exceeds project max_gpu_minutes={max_gpu}"))
        steps.append(step)

    ids = {s.id for s in steps}
    for step in steps:
        for dep in step.after:
            if dep not in ids:
                errors.append(ValidationError(f"step {step.id!r} depends on unknown step {dep!r}"))

    if _has_cycle(steps):
        errors.append(ValidationError("plan graph has a cycle"))

    return steps, errors


def _has_cycle(steps: list[PlanStep]) -> bool:
    graph = {s.id: s.after for s in steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph and dfs(dep):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    return any(dfs(s.id) for s in steps)


def plan_project(
    project: ProjectSpec,
    gaps: list[str],
    router: LlmRouter,
    route: list[str],
    known_caps: set[str],
    constraints: dict[str, Any] | None = None,
    **llm_kwargs,
) -> tuple[list[PlanStep], bool]:
    """§6.2.3's full pipeline, with the same "regenerate once, else fall
    back" discipline comparator_v2's claim guard uses. [FOUND via a real
    LLM call: even a well-constrained prompt listing every known
    capability by name, a small model at low reasoning effort still
    invented 'data_prepare' instead of using 'data_prep' — this isn't
    rare enough to treat as a one-off, so the retry/fallback path is
    real application logic, not a hack for one test.] Returns
    (steps, used_template_fallback)."""
    constraints = constraints or {}
    template_steps = load_template(project.kind)

    adapted = adapt_plan(project, template_steps, gaps, router, route, **llm_kwargs)
    steps, errors = validate_plan(adapted, known_caps, constraints)
    if not errors:
        return steps, False

    retry_raw = adapt_plan(
        project, template_steps, gaps, router, route,
        validation_feedback=str([e.reason for e in errors]), **llm_kwargs,
    )
    steps, errors = validate_plan(retry_raw, known_caps, constraints)
    if not errors:
        return steps, False

    # fall back to the plain template, which we already know validates clean
    fallback_steps, fallback_errors = validate_plan(template_steps, known_caps, constraints)
    assert not fallback_errors, "a shipped template must always validate clean"
    return fallback_steps, True


def ready_steps(steps: list[PlanStep], completed_ids: set[str], started_ids: set[str]) -> list[PlanStep]:
    """§6.2.4: deps done, not started."""
    return [s for s in steps if s.id not in started_ids and all(dep in completed_ids for dep in s.after)]
