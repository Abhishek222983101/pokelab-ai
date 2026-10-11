"""`python -m pokelab_brain.doctor` — the LLM/cloud half of §5.10's
preflight (the GPU/disk/assets half lives in labd's Rust doctor.rs;
this module owns the checks only brain has credentials/clients for).
Prints a ✅/⚠️/❌ line per check and exits non-zero if any check fails,
matching labd doctor's own convention (`just doctor` runs both).

Every network check here makes a REAL call — Elevate and Groq each get
a genuine one-token completion, not a HEAD request or a guess — because
a provider that accepts a TCP connection but 403s on auth is exactly
the failure mode worth catching before a demo.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str


def _load_env_key(name: str) -> str | None:
    """Same convention this repo's tests already use: real env var first,
    then a literal line in .env — never a hardcoded fallback."""
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


def check_elevate() -> CheckResult:
    key = _load_env_key("ELEVATE_TEAM_API_KEY")
    if not key:
        return CheckResult("elevate_gateway", "warn", "no ELEVATE_TEAM_API_KEY — router falls back to Groq-only")
    from pokelab_brain.llm.providers import ElevateProvider, ProviderError

    provider = ElevateProvider(key)
    try:
        resp = provider.complete(
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
            model="gpt-5.6-luna",
            max_tokens=10,
        )
        return CheckResult("elevate_gateway", "ok", f"real completion in {resp.elapsed_s:.2f}s ({resp.model})")
    except ProviderError as e:
        return CheckResult("elevate_gateway", "fail", f"{e}")
    finally:
        provider.close()


def check_groq() -> CheckResult:
    key = _load_env_key("GROQ_API_KEY_1")
    if not key:
        return CheckResult("groq", "warn", "no GROQ_API_KEY_1 — router falls back to Elevate-only")
    from pokelab_brain.llm.providers import GroqProvider, ProviderError

    provider = GroqProvider(key)
    try:
        resp = provider.complete(
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
            model=provider.models[0],
            max_tokens=10,
        )
        return CheckResult("groq", "ok", f"real completion in {resp.elapsed_s:.2f}s ({resp.model})")
    except ProviderError as e:
        return CheckResult("groq", "fail", f"{e}")
    finally:
        provider.close()


def check_kaggle_auth() -> CheckResult:
    kaggle_json = os.path.expanduser("~/.kaggle/kaggle.json")
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return CheckResult("kaggle_auth", "ok", "KAGGLE_USERNAME/KAGGLE_KEY set")
    if os.path.exists(kaggle_json):
        return CheckResult("kaggle_auth", "ok", f"{kaggle_json} present")
    return CheckResult("kaggle_auth", "warn", "no kaggle credentials — remote Kaggle runs unavailable, GPU-local/CPU kits unaffected")


def check_colab_auth() -> CheckResult:
    # there is no official `colab sessions` CLI — what we actually have is
    # a runtime URL + token for workers/pokelab_workers/remote/colab_runner.py
    if os.environ.get("COLAB_RUNTIME_URL") and os.environ.get("COLAB_RUNTIME_TOKEN"):
        return CheckResult("colab_auth", "ok", "COLAB_RUNTIME_URL/COLAB_RUNTIME_TOKEN set")
    return CheckResult("colab_auth", "warn", "no Colab runtime configured — remote Colab runs unavailable, GPU-local/CPU kits unaffected")


def check_wandb_mode() -> CheckResult:
    mode = os.environ.get("WANDB_MODE", "offline")
    if mode == "offline":
        return CheckResult("wandb_mode", "ok", "offline (default, §11.6 — no API key reaches worker processes)")
    if os.environ.get("WANDB_API_KEY"):
        return CheckResult("wandb_mode", "ok", f"mode={mode}, WANDB_API_KEY set")
    return CheckResult("wandb_mode", "warn", f"mode={mode} but no WANDB_API_KEY — online sync will fail")


def check_gateway_cli() -> CheckResult:
    found = subprocess.run(["which", "kaggle"], capture_output=True, text=True).returncode == 0
    return CheckResult(
        "kaggle_cli", "ok" if found else "warn",
        "kaggle CLI on PATH" if found else "kaggle CLI not found — remote Kaggle runs unavailable",
    )


def run() -> list[CheckResult]:
    return [
        check_elevate(),
        check_groq(),
        check_kaggle_auth(),
        check_gateway_cli(),
        check_colab_auth(),
        check_wandb_mode(),
    ]


def main() -> int:
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
    results = run()
    for r in results:
        print(f"{icon[r.status]} {r.name:<16} {r.detail}")
    if any(r.status == "fail" for r in results):
        print("\nError: one or more doctor checks failed — see above", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
