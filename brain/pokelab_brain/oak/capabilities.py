"""Capability analysis (§6.2.2): what does THIS project actually need,
and does the roster cover it? The LLM proposes required capabilities
(constrained to the known taxonomy, but may propose new ones); coverage
is computed by code (Scout + Selector), never claimed by the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pokelab_brain.llm.jsonio import extract_json
from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.oak.intake import ProjectSpec
from pokelab_labml.selector.thompson import ThompsonSelector

KNOWN_CAPABILITIES = {
    "paper_read", "spec_extract", "claim_extract", "implement", "code_edit",
    "env_setup", "dependency_fix", "data_prep", "debug", "repair",
    "experiment_design", "whatif_design", "run_experiment", "compute_ops",
    "remote_run", "analyze", "repro_compare", "explain", "report_write",
    "notes", "author_email", "literature_search", "paper_discover",
}


@dataclass
class RequiredCapability:
    cap: str
    why: str
    weight: float
    is_new: bool = False


@dataclass
class CapabilityAnalysis:
    required: list[RequiredCapability]
    coverage: dict[str, float]
    gaps: list[str] = field(default_factory=list)


_ANALYSIS_PROMPT = """What capabilities does this research project need?

Project: {title} ({kind})
Goal: {goal}
Papers: {papers}

Reply with ONLY a JSON array (no prose, no code fence) of objects shaped:
{{"cap": "<name>", "why": "<one short reason>", "weight": <0-1>, "new": <true|false>}}

Prefer these known capabilities where they fit: {known}
You may propose a genuinely new capability (new=true) with a clear description in "why"
if nothing in the known list covers it.
"""


def analyze_capabilities(
    project: ProjectSpec,
    agent_capabilities: dict[str, list[str]],
    selector: ThompsonSelector,
    router: LlmRouter,
    route: list[str],
    coverage_threshold: float = 0.55,
    **llm_kwargs,
) -> CapabilityAnalysis:
    prompt = _ANALYSIS_PROMPT.format(
        title=project.title, kind=project.kind, goal=project.goal, papers=project.papers,
        known=sorted(KNOWN_CAPABILITIES),
    )
    result = router.complete(messages=[{"role": "user", "content": prompt}], route=route, max_tokens=600, **llm_kwargs)
    parsed = extract_json(result.content)
    if not isinstance(parsed, list):
        raise ValueError(f"capability analysis did not return a JSON array: {result.content!r}")

    required = [
        RequiredCapability(cap=item["cap"], why=item.get("why", ""), weight=float(item.get("weight", 1.0)), is_new=bool(item.get("new", False)))
        for item in parsed
        if isinstance(item, dict) and "cap" in item
    ]

    # coverage by code, not the LLM: for each required cap, the best
    # posterior mean among agents that actually declare it (0.0 if none do)
    coverage: dict[str, float] = {}
    for rc in required:
        agents_with_cap = [agent_id for agent_id, caps in agent_capabilities.items() if rc.cap in caps]
        if not agents_with_cap:
            coverage[rc.cap] = 0.0
            continue
        coverage[rc.cap] = max(selector.mean_estimate(agent_id) for agent_id in agents_with_cap)

    gaps = [rc.cap for rc in required if coverage.get(rc.cap, 0.0) < coverage_threshold]

    return CapabilityAnalysis(required=required, coverage=coverage, gaps=gaps)
