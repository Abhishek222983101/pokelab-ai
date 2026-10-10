import os

import pytest

from pokelab_brain.oak.intake import ProjectSpec, intake


def test_template_matched_request_skips_llm():
    spec = intake("Please reproduce the grokking paper")
    assert spec.kind == "reproduce"
    assert spec.papers == ["grokking"]


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
def test_real_intake_for_free_text_question(tmp_path):
    from pokelab_brain.llm.providers import GroqProvider
    from pokelab_brain.llm.router import LlmRouter

    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db",
    )
    try:
        spec = intake(
            "What happens to grokking if we set weight decay to zero?",
            router=router, route=["groq"], model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert isinstance(spec, ProjectSpec)
    assert spec.kind in ("whatif", "reproduce", "explore")
    assert "grokking" in spec.papers
