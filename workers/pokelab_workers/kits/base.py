"""KitSpec: the interface every training kit implements. A kit is a pure
function of (config, emit, stop) -> final_metrics — it has no idea it is
running inside a warm pool, under labd, or standalone for a benchmark
script. That's what keeps `scripts/reference/*` portable into here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

# emit(step, key, value) -> None
EmitFn = Callable[[int, str, float | None], None]


class StopToken(Protocol):
    def is_set(self) -> bool: ...


class SimpleStopToken:
    """A StopToken that is never set — used standalone / in tests where no
    external stop signal exists yet."""

    def is_set(self) -> bool:
        return False


@dataclass
class KitContext:
    job_id: str
    config: dict[str, Any]
    emit: EmitFn
    stop: StopToken


class Kit(Protocol):
    name: str
    version: str

    def run(self, ctx: KitContext) -> dict[str, Any]:
        """Run to completion (or until ctx.stop.is_set()) and return the
        final metrics dict. Must call ctx.emit() at least once per step that
        matters for the live curve."""
        ...


KIT_REGISTRY: dict[str, Kit] = {}


def register(kit: Kit) -> Kit:
    KIT_REGISTRY[kit.name] = kit
    return kit


def get_kit(name: str) -> Kit:
    if name not in KIT_REGISTRY:
        raise KeyError(f"unknown kit {name!r}; registered: {sorted(KIT_REGISTRY)}")
    return KIT_REGISTRY[name]
