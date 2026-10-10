import os

import pytest

from pokelab_brain.agents.refine import decide_promotion, reflect_and_rewrite
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


def test_decide_promotion_accepts_clean_improvement():
    d = decide_promotion(old_rewards=[0.5, 0.5, 0.5], new_rewards=[0.6, 0.6, 0.6])
    assert d.promote
    assert d.mean_delta > 0.05


def test_decide_promotion_rejects_small_improvement():
    d = decide_promotion(old_rewards=[0.5, 0.5], new_rewards=[0.52, 0.52])
    assert not d.promote


def test_decide_promotion_rejects_a_bad_regression_even_with_good_mean():
    # mean improves a lot, but one task cratered — Pareto rule rejects it
    d = decide_promotion(old_rewards=[0.5, 0.5], new_rewards=[0.9, 0.2])
    assert not d.promote
    assert d.max_regression > 0.10


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_reflection_call_rewrites_the_prompt(tmp_path):
    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db",
        budget_db=tmp_path / "b.db",
    )
    traces = [
        {"task": "run_kit grokking", "success": False, "reward": 0.1, "medic_class": "unknown_kit"},
        {"task": "run_kit grokking", "success": False, "reward": 0.15, "medic_class": "unknown_kit"},
        {"task": "run_kit smoke", "success": True, "reward": 0.9, "medic_class": "none"},
    ]
    try:
        new_prompt = reflect_and_rewrite(
            router, route=["groq"], current_prompt="You are a research agent. Use run_kit.",
            traces=traces, model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert len(new_prompt) > 20
    assert new_prompt != "You are a research agent. Use run_kit."
