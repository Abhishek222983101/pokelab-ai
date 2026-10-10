import os

import pytest

from pokelab_brain.oak.capabilities import analyze_capabilities
from pokelab_brain.oak.intake import ProjectSpec
from pokelab_labml.selector.thompson import ThompsonSelector


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
def test_real_capability_analysis_for_grokking_reproduction(tmp_path):
    from pokelab_brain.llm.providers import GroqProvider
    from pokelab_brain.llm.router import LlmRouter

    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db",
    )
    project = ProjectSpec(title="Reproduce grokking", kind="reproduce", goal="Reproduce the grokking paper", papers=["grokking"])

    selector = ThompsonSelector()
    selector.record_outcome("eevee-1", 0.9)  # eevee-1 is good at whatever it does
    agent_capabilities = {"eevee-1": ["run_experiment", "paper_read"]}

    try:
        analysis = analyze_capabilities(
            project, agent_capabilities, selector, router, route=["groq"],
            model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert len(analysis.required) > 0
    cap_names = {rc.cap for rc in analysis.required}
    # a reproduction task should ask for at least reading the paper and running an experiment
    assert "paper_read" in cap_names or "run_experiment" in cap_names
    # coverage must be code-computed numbers in [0, 1], never missing
    for rc in analysis.required:
        assert 0.0 <= analysis.coverage[rc.cap] <= 1.0


def test_coverage_and_gaps_are_computed_by_code_not_llm():
    """A fake router lets us pin the LLM's output and check ONLY the
    coverage math, which must never come from the LLM."""
    class FakeRouter:
        def complete(self, messages, route, **kwargs):
            class R:
                content = '[{"cap": "run_experiment", "why": "x", "weight": 1.0}, {"cap": "analyze_3d", "why": "y", "weight": 0.8, "new": true}]'
            return R()

    selector = ThompsonSelector()
    selector.record_outcome("eevee-1", 0.9)
    agent_capabilities = {"eevee-1": ["run_experiment"]}  # covers run_experiment, NOT analyze_3d

    project = ProjectSpec(title="x", kind="reproduce", goal="x", papers=["grokking"])
    analysis = analyze_capabilities(project, agent_capabilities, selector, FakeRouter(), route=["fake"])

    assert analysis.coverage["run_experiment"] > 0.55
    assert analysis.coverage["analyze_3d"] == 0.0
    assert analysis.gaps == ["analyze_3d"]
