"""The `smoke` kit: proves the protocol end to end without torch, a GPU, or
any real model. 50 steps, < 1 s on CPU, honours stop within one step."""
from __future__ import annotations

import time
from typing import Any

from pokelab_workers.kits.base import KitContext, register


class SmokeKit:
    name = "smoke"
    version = "1"

    def run(self, ctx: KitContext) -> dict[str, Any]:
        n_steps = int(ctx.config.get("n_steps", 50))
        value = 1.0
        for step in range(1, n_steps + 1):
            if ctx.stop.is_set():
                return {"stopped_at": step, "value": value}
            value *= 0.95
            ctx.emit(step, "loss", value)
            if n_steps > 500:
                time.sleep(0.001)
        return {"final_loss": value, "n_steps": n_steps}


kit = register(SmokeKit())
