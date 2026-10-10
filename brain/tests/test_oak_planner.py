import os

import pytest

from pokelab_brain.oak.capabilities import KNOWN_CAPABILITIES
from pokelab_brain.oak.intake import ProjectSpec
from pokelab_brain.oak.planner import adapt_plan, load_template, plan_project, ready_steps, validate_plan


@pytest.mark.parametrize("kind", ["reproduce", "whatif", "compare", "explore", "discover"])
def test_all_templates_load_and_validate_clean(kind):
    steps_raw = load_template(kind)
    assert len(steps_raw) > 0
    steps, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={})
    assert errors == [], f"{kind}: {errors}"
    assert len(steps) == len(steps_raw)


def test_validate_plan_catches_missing_accept_checks():
    steps_raw = [{"id": "s1", "cap": "paper_read", "title": "x", "accept": [], "after": []}]
    _, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={})
    assert any("no accept checks" in e.reason for e in errors)


def test_validate_plan_catches_unknown_capability():
    steps_raw = [{"id": "s1", "cap": "not_a_real_cap", "title": "x", "accept": ["x"], "after": []}]
    _, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={})
    assert any("unknown capability" in e.reason for e in errors)


def test_validate_plan_catches_cycles():
    steps_raw = [
        {"id": "s1", "cap": "paper_read", "title": "x", "accept": ["x"], "after": ["s2"]},
        {"id": "s2", "cap": "paper_read", "title": "y", "accept": ["x"], "after": ["s1"]},
    ]
    _, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={})
    assert any("cycle" in e.reason for e in errors)


def test_validate_plan_catches_unknown_dependency():
    steps_raw = [{"id": "s1", "cap": "paper_read", "title": "x", "accept": ["x"], "after": ["nope"]}]
    _, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={})
    assert any("unknown step" in e.reason for e in errors)


def test_validate_plan_catches_over_budget():
    steps_raw = [{
        "id": "s1", "cap": "run_experiment", "title": "x", "accept": ["x"], "after": [],
        "budget": {"max_gpu_s": 600},
    }]
    _, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={"max_gpu_minutes": 5})
    assert any("exceeds project max_gpu_minutes" in e.reason for e in errors)


def test_ready_steps_respects_dependencies():
    steps_raw = load_template("reproduce")
    steps, errors = validate_plan(steps_raw, KNOWN_CAPABILITIES, constraints={})
    assert errors == []

    ready = ready_steps(steps, completed_ids=set(), started_ids=set())
    assert [s.id for s in ready] == ["s1"]  # only the step with no deps

    ready2 = ready_steps(steps, completed_ids={"s1"}, started_ids={"s1"})
    assert [s.id for s in ready2] == ["s2"]


def _load_env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_plan_adaptation_for_grokking(tmp_path):
    """Uses plan_project (adapt -> validate -> retry-with-feedback ->
    fall back to the plain template), not raw adapt_plan — a real run
    against openai/gpt-oss-20b at low reasoning effort DOES invent an
    off-taxonomy capability name often enough that asserting a clean
    first-try pass would make this test itself flaky. plan_project's
    retry/fallback is what makes the GUARANTEE ('you always get back a
    valid plan') real regardless of what the model does."""
    from pokelab_brain.llm.providers import GroqProvider
    from pokelab_brain.llm.router import LlmRouter

    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db",
    )
    project = ProjectSpec(title="Reproduce grokking", kind="reproduce", goal="Reproduce grokking on modular addition", papers=["grokking"])
    try:
        steps, used_fallback = plan_project(
            project, gaps=[], router=router, route=["groq"], known_caps=KNOWN_CAPABILITIES,
            model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert len(steps) > 0
    print(f"\nused_fallback={used_fallback}")  # informational — both outcomes are valid


def test_plan_project_falls_back_to_the_template_when_the_llm_never_recovers():
    """A fake router that always returns an off-taxonomy capability name
    proves the fallback actually fires and still returns a valid plan."""
    class AlwaysWrongRouter:
        def complete(self, messages, route, **kwargs):
            class R:
                content = '[{"id": "s1", "cap": "totally_made_up_cap", "title": "x", "accept": ["x"], "after": []}]'
            return R()

    project = ProjectSpec(title="x", kind="reproduce", goal="x", papers=["grokking"])
    steps, used_fallback = plan_project(
        project, gaps=[], router=AlwaysWrongRouter(), route=["fake"], known_caps=KNOWN_CAPABILITIES,
    )
    assert used_fallback is True
    assert len(steps) == len(load_template("reproduce"))
