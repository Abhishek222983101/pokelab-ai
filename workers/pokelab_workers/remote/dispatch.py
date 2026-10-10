"""The remote runner protocol (§P10.1): one shape, two backends. Every
runner (local warm pool, Colab, Kaggle) emits the same {"t": ...} lines
(pokelab_workers.protocol) — this module is the single place that picks
which backend actually runs a job, using labml's Compute Router.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pokelab_labml.router.placement import choose_placement
from pokelab_workers.remote.colab_runner import run_on_colab
from pokelab_workers.remote.kaggle_runner import push_and_run


@dataclass
class DispatchResult:
    target: str
    reason: str
    protocol_lines: list[dict[str, Any]]


def dispatch(
    *,
    estimated_wall_s: float,
    local_free_slots: int,
    local_vram_headroom_mib: float,
    required_vram_mib: float,
    script_path: str,
    kaggle_kernel_dir: str | None = None,
    kaggle_slug: str | None = None,
    kaggle_username: str | None = None,
) -> DispatchResult:
    """Only decides local vs. remote and, if remote, which remote — it
    never submits to the LOCAL warm pool itself (that's lab_jobs.WarmPool's
    job, already wired through labd). A "local" decision here means "the
    caller should use the warm pool," not that this function does it."""
    decision = choose_placement(
        estimated_wall_s=estimated_wall_s,
        local_free_slots=local_free_slots,
        local_vram_headroom_mib=local_vram_headroom_mib,
        required_vram_mib=required_vram_mib,
    )

    if decision.target == "local":
        return DispatchResult(target="local", reason=decision.reason, protocol_lines=[])

    if decision.target == "colab":
        result = run_on_colab(script_path, gpu="T4", timeout_s=max(60, int(estimated_wall_s * 2)))
        return DispatchResult(target="colab", reason=decision.reason, protocol_lines=result.protocol_lines)

    if decision.target == "kaggle":
        if not (kaggle_kernel_dir and kaggle_slug and kaggle_username):
            raise ValueError("kaggle dispatch needs kaggle_kernel_dir, kaggle_slug and kaggle_username")
        result = push_and_run(
            kernel_dir=kaggle_kernel_dir, slug=kaggle_slug, username=kaggle_username,
            script_name=script_path, timeout_s=max(120, estimated_wall_s * 3),
        )
        return DispatchResult(target="kaggle", reason=decision.reason, protocol_lines=result.protocol_lines)

    raise ValueError(f"unknown placement target: {decision.target}")
