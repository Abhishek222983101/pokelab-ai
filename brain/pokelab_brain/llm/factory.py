"""Production LlmRouter construction (§6.5): Elevate first, Groq as fallback, keys from the
environment or the gitignored .env — never from config files or code. Returns None when no key is
available, so callers degrade honestly (e.g. Oak only accepts requests that name a known paper).
"""
from __future__ import annotations

import os
from pathlib import Path

from pokelab_brain.llm.providers import ElevateProvider, GroqProvider, Provider
from pokelab_brain.llm.router import LlmRouter

ROOT = Path(__file__).resolve().parents[3]


def env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip().startswith(f"{name}="):
                return line.strip().split("=", 1)[1] or None
    return None


def build_router() -> tuple[LlmRouter, list[str]] | None:
    providers: dict[str, Provider] = {}
    if key := env_key("ELEVATE_TEAM_API_KEY"):
        providers["elevate"] = ElevateProvider(key)
    if key := env_key("GROQ_API_KEY_1"):
        providers["groq"] = GroqProvider(key)
    if not providers:
        return None
    var = ROOT / "var"
    var.mkdir(exist_ok=True)
    router = LlmRouter(providers=providers, cache_db=var / "llm_cache.db", budget_db=var / "brain.db")
    route = [p for p in ("elevate", "groq") if p in providers]
    return router, route
