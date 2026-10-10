"""LLM providers, both exposed as OpenAI-compatible chat completions
(§6.5). Elevate is the primary route; Groq is the fallback (and the
interactive-first route, since it's faster and has no team-wide quota
fight — §13.0.4/[MEASURED]).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx


class ProviderError(Exception):
    """Raised with enough structure for the router to decide: retry the
    same provider, fall back to the next one, or give up."""

    def __init__(self, message: str, status_code: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    @property
    def is_quota_exhausted(self) -> bool:
        return self.status_code == 403


@dataclass
class ProviderResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_s: float
    raw: dict[str, Any] = field(default_factory=dict)


class Provider:
    """Common shape both providers share: OpenAI's chat/completions."""

    name: str
    base_url: str
    models: list[str]

    def __init__(self, api_key: str, base_url: str, models: list[str], user_agent: str | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self.models = models
        headers = {"Authorization": f"Bearer {api_key}"}
        if user_agent:
            headers["User-Agent"] = user_agent
        # §13.0.4 pin: max_retries=0 — the ROUTER owns retry/fallback
        # policy, not the HTTP client (a client-level retry would hide a
        # 429 from the budget/circuit-breaker logic).
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=httpx.Timeout(connect=5, read=45, write=10, pool=5))

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 512,
        **extra: Any,
    ) -> ProviderResponse:
        model = model or self.models[0]
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            **extra,
        }
        t0 = time.perf_counter()
        try:
            resp = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise ProviderError(f"{self.name} timeout: {e}") from e
        elapsed = time.perf_counter() - t0

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", 60))
            raise ProviderError(f"{self.name} rate limited", status_code=429, retry_after=retry_after)
        if resp.status_code == 403:
            raise ProviderError(f"{self.name} quota exhausted", status_code=403)
        if resp.status_code >= 400:
            raise ProviderError(f"{self.name} HTTP {resp.status_code}: {resp.text[:300]}", status_code=resp.status_code)

        data = resp.json()
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        return ProviderResponse(
            content=choice.get("content") or "",
            model=data.get("model", model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            elapsed_s=elapsed,
            raw=data,
        )

    def close(self) -> None:
        self._client.close()


class ElevateProvider(Provider):
    """The hackathon's shared gateway. [MEASURED facts, §13.0.4]: no
    tool-calling, no JSON-schema enforcement, 48 KB max request, ~10 rapid
    calls -> 429, 800k tokens/day shared team budget resetting 00:00 UTC.
    """

    name = "elevate"

    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            base_url="https://elevate1-0.vercel.app/api/ai",
            models=["gpt-5.6-luna", "deepseek-v4-pro", "gpt-5-mini"],
        )


class GroqProvider(Provider):
    """Fallback / interactive-first provider. [MEASURED]: ~0.3s latency on
    openai/gpt-oss-20b, 8000 tok/min and 1000 req/day PER ORG (shared across
    both keys, not per key) — needs a non-default User-Agent or Groq
    returns 403."""

    name = "groq"

    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            models=["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"],
            user_agent="PokeLab/1.0 (+hackathon demo)",
        )
