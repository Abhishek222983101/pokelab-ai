import os

import pytest

from pokelab_brain.agents.spawn import draft_spec
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


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_spawn_draft_for_a_3d_analysis_gap(tmp_path):
    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db",
        budget_db=tmp_path / "b.db",
    )
    nearest = [AgentSpec(id="eevee-0", species="eevee", role="generalist", capabilities=["run_kit", "read_paper"], prompt_ref="generalist.md")]
    try:
        spec, prompt_summary = draft_spec(
            router, route=["groq"], capability="analyze_3d",
            nearest_agents=nearest, past_spawns=[],
            model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert isinstance(spec, AgentSpec)
    assert spec.status == "proposed"
    assert "analyze_3d" in spec.capabilities
    assert len(prompt_summary) > 0
