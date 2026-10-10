import os
import tempfile

import pytest

from pokelab_brain.llm.providers import GroqProvider, Provider, ProviderError, ProviderResponse
from pokelab_brain.llm.router import AllProvidersExhausted, LlmRouter


def _load_env_key(name: str) -> str | None:
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


class AlwaysFailsProvider(Provider):
    name = "flaky"

    def __init__(self):
        self.closed = False

    def complete(self, messages, model=None, max_tokens=512, **extra):
        raise ProviderError("simulated outage", status_code=429, retry_after=1.0)

    def close(self):
        self.closed = True


class CannedProvider(Provider):
    name = "canned"

    def __init__(self, content="canned response"):
        self.content = content
        self.calls = 0

    def complete(self, messages, model=None, max_tokens=512, **extra):
        self.calls += 1
        return ProviderResponse(
            content=self.content, model="canned-model",
            prompt_tokens=10, completion_tokens=5, elapsed_s=0.01,
        )

    def close(self):
        pass


@pytest.fixture
def router(tmp_path):
    providers = {"canned": CannedProvider()}
    r = LlmRouter(
        providers=providers,
        cache_db=tmp_path / "llm_cache.db",
        budget_db=tmp_path / "brain.db",
    )
    yield r
    r.close()


def test_cache_hit_on_second_identical_call(router):
    messages = [{"role": "user", "content": "hello"}]
    r1 = router.complete(messages, route=["canned"])
    assert r1.cached is False
    assert router.providers["canned"].calls == 1

    r2 = router.complete(messages, route=["canned"])
    assert r2.cached is True
    assert r2.content == r1.content
    assert router.providers["canned"].calls == 1  # not called again


def test_fallback_skips_a_failing_provider(tmp_path):
    providers = {"flaky": AlwaysFailsProvider(), "canned": CannedProvider("from the fallback")}
    r = LlmRouter(providers=providers, cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db")
    try:
        result = r.complete([{"role": "user", "content": "x"}], route=["flaky", "canned"])
        assert result.provider == "canned"
        assert result.content == "from the fallback"
    finally:
        r.close()


def test_all_providers_exhausted_raises(tmp_path):
    providers = {"flaky": AlwaysFailsProvider()}
    r = LlmRouter(providers=providers, cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db")
    try:
        with pytest.raises(AllProvidersExhausted):
            r.complete([{"role": "user", "content": "x"}], route=["flaky"])
    finally:
        r.close()


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_groq_through_the_router(tmp_path):
    providers = {"groq": GroqProvider(GROQ_KEY)}
    r = LlmRouter(providers=providers, cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db")
    try:
        result = r.complete(
            [{"role": "user", "content": "Reply with exactly the word: pong"}],
            route=["groq"],
            model="openai/gpt-oss-20b",
            max_tokens=50,
            reasoning_effort="low",
        )
        assert "pong" in result.content.lower()
        assert result.provider == "groq"
        assert not result.cached

        used, requests = r.budget.used_today("groq")
        assert used > 0
        assert requests >= 1
    finally:
        r.close()
