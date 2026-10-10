import os

import pytest

from pokelab_brain.agents.merge import decide_merge, synthesize
from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.llm.providers import GroqProvider
from pokelab_brain.llm.router import LlmRouter


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


def test_decide_merge_accepts_near_parent_performance():
    d = decide_merge(merged_rewards=[0.72, 0.70], parent_a_mean=0.70, parent_b_mean=0.60)
    assert d.accept


def test_decide_merge_rejects_clear_underperformance():
    d = decide_merge(merged_rewards=[0.4, 0.4], parent_a_mean=0.70, parent_b_mean=0.60)
    assert not d.accept


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_merge_synthesis(tmp_path):
    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db",
        budget_db=tmp_path / "b.db",
    )
    a = AgentSpec(id="eevee-1", species="eevee", role="paper_reader", capabilities=["read_paper", "run_kit"], prompt_ref="a.md")
    b = AgentSpec(id="eevee-2", species="eevee", role="kit_runner", capabilities=["run_kit", "analyze"], prompt_ref="b.md")
    try:
        spec, summary = synthesize(
            router, route=["groq"], agent_a=a, prompt_a="Read papers carefully, cite sections.",
            agent_b=b, prompt_b="Run kits and report metrics precisely.", new_id="eevee-merged-1",
            model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert spec.parent_ids == ["eevee-1", "eevee-2"]
    assert "read_paper" in spec.capabilities and "run_kit" in spec.capabilities and "analyze" in spec.capabilities
    assert len(summary) > 0
