"""The `run_kit` tool: an agent's only path to real compute. Submits via
the bus, then waits on the state projection's job-done event — the
*same* event stream a human watching the console sees, so there is no
special "agent fast path" that could show something the UI didn't.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pokelab_brain.bus import BrainBus
from pokelab_brain.state import StateProjection

TOOL_NAME = "run_kit"
TOOL_DESCRIPTION = (
    '{"tool": "run_kit", "args": {"kit": "grokking|smoke|...", "config": {...}}, '
    '"returns": {"job_id": str, "status": "ok|stopped|error", "final": {...}, "error_sig": str|None}}'
)


@dataclass
class ToolContext:
    bus: BrainBus
    state: StateProjection
    project: str | None = None
    timeout_s: float = 120.0


async def run_kit(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    kit = args.get("kit")
    config = args.get("config", {})
    if not kit:
        return {"error": "run_kit requires an 'kit' argument"}

    req = f"tool-run_kit-{asyncio.get_event_loop().time()}"
    try:
        job_id = await ctx.bus.job_submit(kit, config, req=req, project=ctx.project)
    except RuntimeError as e:
        return {"error": str(e)}

    done = ctx.state.job_done_event(job_id)
    try:
        await asyncio.wait_for(done.wait(), timeout=ctx.timeout_s)
    except asyncio.TimeoutError:
        return {"job_id": job_id, "status": "timeout", "final": None, "error_sig": None}

    job = ctx.state.jobs[job_id]
    return {"job_id": job_id, "status": job.status, "final": job.final, "error_sig": job.error_sig}
