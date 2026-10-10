"""Our own agent action protocol (chosen because Elevate supports neither
tool-calling nor JSON-schema enforcement — §13.0.4 [MEASURED]). An agent's
reply is free text containing up to three tagged sections:

    <thought>...free reasoning...</thought>
    <action tool="run_kit">{"kit": "grokking", "config": {...}}</action>
    <final>{"summary": "...", "result": {...}}</final>

Exactly one of <action> or <final> should be present per turn; if both or
neither are, we pick the most sensible interpretation rather than erroring
the whole turn, because asking a small/free model to be perfectly well-
formed every time is not realistic (§6.9.1 — tested against real replies
plus fuzz in test_protocol.py).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pokelab_brain.llm.jsonio import extract_json

_THOUGHT_RE = re.compile(r"<thought>(.*?)</thought>", re.DOTALL | re.IGNORECASE)
_ACTION_RE = re.compile(
    r'<action\s+tool\s*=\s*"([^"]+)"\s*>(.*?)</action>', re.DOTALL | re.IGNORECASE
)
_FINAL_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)


@dataclass
class ActionCall:
    tool: str
    args: dict[str, Any]


@dataclass
class ParsedResponse:
    thought: str | None
    action: ActionCall | None
    final: dict[str, Any] | None
    raw: str
    malformed: bool = False  # true if we had to guess/repair something


def parse_response(text: str) -> ParsedResponse:
    thought_match = _THOUGHT_RE.search(text)
    thought = thought_match.group(1).strip() if thought_match else None

    final_match = _FINAL_RE.search(text)
    action_match = _ACTION_RE.search(text)

    malformed = False

    final: dict[str, Any] | None = None
    if final_match:
        final = extract_json(final_match.group(1))
        if final is None:
            # model wrote <final>some prose, not json</final> — wrap it so
            # the loop can still terminate instead of looping forever
            final = {"summary": final_match.group(1).strip()}
            malformed = True

    action: ActionCall | None = None
    if action_match:
        tool = action_match.group(1).strip()
        args = extract_json(action_match.group(2))
        if args is None:
            args = {}
            malformed = True
        action = ActionCall(tool=tool, args=args)

    if final is not None and action is not None:
        # a model that emits both is treating <final> as "I'm done" — honor
        # that over the action, but flag it so callers can log/penalize
        action = None
        malformed = True

    if final is None and action is None and thought is None:
        # no tags at all — the WHOLE reply is salvaged as a thought so the
        # conversation can continue (the router will re-prompt for a
        # properly-tagged turn) rather than crashing the agent loop
        thought = text.strip()
        malformed = True

    return ParsedResponse(thought=thought, action=action, final=final, raw=text, malformed=malformed)


def format_tool_result(tool: str, result: Any) -> str:
    """How a tool's result is handed back to the model on the next turn."""
    return f"<tool_result tool=\"{tool}\">{json.dumps(result)}</tool_result>"
