"""The LLM router: tries providers in order, respects each one's local
rate limiter and daily budget, falls back on 429/403/timeout, and caches
every response. This is the one place in `brain` that ever calls out to
an LLM — agents and Oak go through here, never straight to `httpx`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pokelab_brain.llm.budget import BudgetTracker
from pokelab_brain.llm.cache import LlmCache, cache_key
from pokelab_brain.llm.providers import Provider, ProviderError, ProviderResponse
from pokelab_brain.llm.ratelimit import SlidingWindowLimiter

logger = logging.getLogger(__name__)

# [MEASURED §13.0.4] — Elevate: ~10 calls/min before 429, 800k tok/day team
# budget. Groq: 8000 tok/min PER ORG (both keys share the bucket), 1000
# req/day per key.
DEFAULT_LIMITS = {
    "elevate": {"calls_per_min": 10, "daily_token_budget": 800_000},
    "groq": {"tokens_per_min": 8000, "daily_token_budget": None},
}


@dataclass
class RouteResult:
    content: str
    provider: str
    model: str
    cached: bool
    elapsed_s: float
    prompt_tokens: int
    completion_tokens: int


class AllProvidersExhausted(Exception):
    def __init__(self, attempts: list[str]):
        super().__init__(f"every provider in the route failed or was rate-limited: {attempts}")
        self.attempts = attempts


class LlmRouter:
    def __init__(
        self,
        providers: dict[str, Provider],
        cache_db: str | Path,
        budget_db: str | Path,
        mode: str = "live",
    ):
        self.providers = providers
        self.cache = LlmCache(cache_db)
        self.budget = BudgetTracker(budget_db)
        self.mode = mode  # live | replay | llm-replay
        self._call_limiters: dict[str, SlidingWindowLimiter] = {}
        self._token_limiters: dict[str, SlidingWindowLimiter] = {}
        for name, limits in DEFAULT_LIMITS.items():
            if "calls_per_min" in limits and limits["calls_per_min"]:
                self._call_limiters[name] = SlidingWindowLimiter(limits["calls_per_min"], 60.0)
            if "tokens_per_min" in limits and limits["tokens_per_min"]:
                self._token_limiters[name] = SlidingWindowLimiter(limits["tokens_per_min"], 60.0)

    def complete(
        self,
        messages: list[dict[str, str]],
        route: list[str],
        model: str | dict[str, str] | None = None,
        max_tokens: int = 512,
        estimate_tokens: int = 200,
        **extra: Any,
    ) -> RouteResult:
        """`model` is either one name used for every provider in `route`
        (fine when they share a model, e.g. two Groq-compatible deployments),
        or a `{provider_name: model_name}` dict — REQUIRED once the route
        mixes providers that don't share model names (Elevate's
        "gpt-5.6-luna" means nothing to Groq, and vice versa). [Found while
        wiring Elevate in as a second provider: a single flat model string
        silently sent the wrong model name to whichever provider wasn't
        first in the route.]"""
        cache_model_hint = model if isinstance(model, str) else (model or {}).get(route[0], route[0])
        key = cache_key(cache_model_hint, messages, max_tokens=max_tokens, **extra)
        cached = self.cache.get(key)
        if cached is not None:
            usage = cached.get("usage", {})
            return RouteResult(
                content=cached["content"],
                provider="cache",
                model=route[0],
                cached=True,
                elapsed_s=0.0,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

        if self.mode == "llm-replay":
            raise AllProvidersExhausted(["llm-replay mode: no cached entry for this prompt"])

        attempts: list[str] = []
        for provider_name in route:
            provider = self.providers.get(provider_name)
            if provider is None:
                continue

            limits = DEFAULT_LIMITS.get(provider_name, {})
            daily_limit = limits.get("daily_token_budget")
            if daily_limit and self.budget.would_exceed(provider_name, daily_limit, estimate_tokens):
                attempts.append(f"{provider_name}: daily budget would be exceeded")
                continue

            call_limiter = self._call_limiters.get(provider_name)
            if call_limiter and call_limiter.would_exceed():
                attempts.append(f"{provider_name}: local call-rate limit reached")
                continue
            token_limiter = self._token_limiters.get(provider_name)
            if token_limiter and token_limiter.would_exceed(estimate_tokens):
                attempts.append(f"{provider_name}: local token-rate limit reached")
                continue

            provider_model = model if isinstance(model, str) or model is None else model.get(provider_name)
            try:
                resp: ProviderResponse = provider.complete(messages, model=provider_model, max_tokens=max_tokens, **extra)
            except ProviderError as e:
                attempts.append(f"{provider_name}: {e}")
                logger.warning("provider %s failed: %s", provider_name, e)
                continue

            if call_limiter:
                call_limiter.record()
            if token_limiter:
                token_limiter.record(resp.prompt_tokens + resp.completion_tokens)
            self.budget.record(provider_name, resp.prompt_tokens + resp.completion_tokens)
            self.cache.put(
                key,
                resp.model,
                {"messages": messages, "max_tokens": max_tokens, **extra},
                resp.content,
                {"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens},
            )
            return RouteResult(
                content=resp.content,
                provider=provider_name,
                model=resp.model,
                cached=False,
                elapsed_s=resp.elapsed_s,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
            )

        raise AllProvidersExhausted(attempts)

    def close(self) -> None:
        self.cache.close()
        self.budget.close()
        for p in self.providers.values():
            p.close()
