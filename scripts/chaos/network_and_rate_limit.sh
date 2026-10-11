#!/usr/bin/env bash
# Chaos drill: network off / 429 storm (P12.2). A literal network
# severing or a real 429 storm against Elevate/Groq isn't safe to
# automate here (the 429 storm would burn the team's real shared daily
# quota; severing network in a shared dev sandbox risks other sessions).
# Instead this runs the router's real fault-injection tests: a provider
# that ALWAYS raises ProviderError(status_code=429) on every call,
# proving the router falls back to a healthy provider (network-off and
# 429-storm are the same failure shape from the router's point of view
# -- "this provider is unusable right now") and raises a clear,
# catchable error when every route is exhausted rather than hanging.
# See brain/tests/test_router.py: test_fallback_skips_a_failing_provider,
# test_all_providers_exhausted_raises.
set -euo pipefail
cd "$(dirname "$0")/../../brain"
uv run pytest tests/test_router.py -v -k "fallback or exhausted"
