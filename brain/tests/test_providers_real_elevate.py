"""A REAL call to the Elevate gateway — not mocked. Skips if the key
isn't in the environment."""
import os

import pytest

from pokelab_brain.llm.providers import ElevateProvider


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


ELEVATE_KEY = _load_env_key("ELEVATE_TEAM_API_KEY")


@pytest.mark.skipif(ELEVATE_KEY is None, reason="no ELEVATE_TEAM_API_KEY available")
def test_elevate_real_completion():
    provider = ElevateProvider(ELEVATE_KEY)
    try:
        resp = provider.complete(
            messages=[{"role": "user", "content": "Reply with exactly the word: pong"}],
            model="gpt-5.6-luna",
            max_tokens=50,
        )
    finally:
        provider.close()

    assert "pong" in resp.content.lower()
    assert resp.prompt_tokens > 0
    assert resp.model.startswith("gpt-5.6-luna")


@pytest.mark.skipif(ELEVATE_KEY is None, reason="no ELEVATE_TEAM_API_KEY available")
def test_elevate_real_completion_through_the_router(tmp_path):
    from pokelab_brain.llm.router import LlmRouter

    router = LlmRouter(
        providers={"elevate": ElevateProvider(ELEVATE_KEY)},
        cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db",
    )
    try:
        result = router.complete(
            [{"role": "user", "content": "Reply with exactly the word: pong"}],
            route=["elevate"], model="gpt-5.6-luna", max_tokens=50,
        )
    finally:
        router.close()

    assert result.provider == "elevate"
    assert "pong" in result.content.lower()
