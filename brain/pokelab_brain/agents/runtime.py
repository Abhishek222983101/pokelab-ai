"""The agent loop: prompt -> parse -> (call a tool | finish) -> repeat.
This is deliberately small — the interesting behaviour lives in the
prompt and the tools, not in control flow here (§6.9).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pokelab_brain.agents.protocol import format_tool_result, parse_response
from pokelab_brain.agents.tools.jobs import ToolContext
from pokelab_brain.llm.router import LlmRouter

logger = logging.getLogger(__name__)

ToolFn = Callable[[dict[str, Any], ToolContext], Awaitable[dict[str, Any]]]


@dataclass
class TurnRecord:
    thought: str | None
    action_tool: str | None
    action_args: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    malformed: bool


@dataclass
class AgentRunResult:
    final: dict[str, Any] | None
    turns: list[TurnRecord] = field(default_factory=list)
    gave_up: bool = False


async def run_agent(
    router: LlmRouter,
    route: list[str],
    system_prompt: str,
    tools: dict[str, ToolFn],
    tool_ctx: ToolContext,
    max_turns: int = 8,
    **llm_kwargs: Any,
) -> AgentRunResult:
    # some models (e.g. Groq's qwen chat template) reject a request with
    # no user-role message at all — a plain "Begin." kickoff keeps this
    # correct chat structure regardless of provider quirks.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Begin."},
    ]
    turns: list[TurnRecord] = []

    for turn_i in range(max_turns):
        result = router.complete(messages, route=route, **llm_kwargs)
        messages.append({"role": "assistant", "content": result.content})
        parsed = parse_response(result.content)

        if parsed.final is not None:
            turns.append(TurnRecord(parsed.thought, None, None, None, parsed.malformed))
            return AgentRunResult(final=parsed.final, turns=turns)

        if parsed.action is not None:
            tool_fn = tools.get(parsed.action.tool)
            if tool_fn is None:
                tool_result = {"error": f"unknown tool {parsed.action.tool!r}; known: {sorted(tools)}"}
            else:
                tool_result = await tool_fn(parsed.action.args, tool_ctx)
            turns.append(TurnRecord(parsed.thought, parsed.action.tool, parsed.action.args, tool_result, parsed.malformed))
            messages.append({"role": "user", "content": format_tool_result(parsed.action.tool, tool_result)})
            continue

        # neither action nor final — nudge the model back into protocol
        turns.append(TurnRecord(parsed.thought, None, None, None, True))
        messages.append({
            "role": "user",
            "content": "Your reply had no <action> or <final> tag. Reply again using exactly the protocol you were given.",
        })

    logger.warning("agent gave up after %d turns without reaching <final>", max_turns)
    return AgentRunResult(final=None, turns=turns, gave_up=True)
