"""JSON extraction from free-text LLM output. Elevate enforces no JSON
schema at all (§13.0.4 [MEASURED]) and even providers that nominally
support `response_format=json_object` sometimes wrap the object in prose
or a markdown code fence — so every caller goes through here instead of
`json.loads` directly.
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",(\s*[\]}])")


def extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Best-effort: try the whole string, then a fenced code block, then
    the widest {...} or [...] span, each with a light repair pass (strip
    trailing commas, strip a leading/trailing prose sentence). Returns
    None rather than raising — callers decide what "the model didn't give
    us JSON" means for them (retry, ask again, fall back)."""
    candidates = _candidates(text)
    for candidate in candidates:
        parsed = _try_parse(candidate)
        if parsed is not None:
            return parsed
    return None


def _candidates(text: str) -> list[str]:
    out = [text.strip()]

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        out.append(fence_match.group(1).strip())

    # widest brace/bracket span — handles "Here is the result: {...} thanks!"
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            out.append(text[start : end + 1])

    return out


def _try_parse(candidate: str) -> dict[str, Any] | list[Any] | None:
    for attempt in (candidate, _TRAILING_COMMA_RE.sub(r"\1", candidate)):
        try:
            value = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            return value
    return None
