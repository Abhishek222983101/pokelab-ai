"""A REAL call to Groq — not mocked. Skips (doesn't fail) if the key isn't
in the environment, so this suite still runs green on a box without
secrets, but on THIS machine it actually hits the network."""
import os

import pytest

from pokelab_brain.llm.providers import GroqProvider


def _load_env_key(name: str) -> str | None:
    # tests run standalone, not through labd, so read .env directly here
    # (brain's real boot path gets it from the process env — see main.py)
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_groq_real_completion():
    provider = GroqProvider(GROQ_KEY)
    try:
        resp = provider.complete(
            messages=[{"role": "user", "content": "Reply with exactly the word: pong"}],
            model="openai/gpt-oss-20b",
            max_tokens=50,
            reasoning_effort="low",
        )
    finally:
        provider.close()

    assert "pong" in resp.content.lower()
    assert resp.prompt_tokens > 0
    assert resp.elapsed_s < 5.0, f"expected Groq to be fast, got {resp.elapsed_s:.2f}s"


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_groq_bad_model_raises_provider_error():
    from pokelab_brain.llm.providers import ProviderError

    provider = GroqProvider(GROQ_KEY)
    try:
        with pytest.raises(ProviderError):
            provider.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="this-model-does-not-exist",
            )
    finally:
        provider.close()
