"""In-memory state, rebuilt purely by folding the event stream (§6.12):
no other source of truth exists on the brain side. A crash just means
reconnecting and replaying from seq 0 (or the last snapshot) — see
`StateProjection.apply`, which is the only place state changes.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pokelab_brain.bus import Event


@dataclass
class JobState:
    job_id: str
    kit: str | None = None
    project: str | None = None
    status: str = "running"
    metrics: dict[str, list[tuple[int, float | None]]] = field(default_factory=dict)
    final: dict[str, Any] | None = None
    error_sig: str | None = None


@dataclass
class StateProjection:
    """Folds `job.*` events into a live view. Agent/project state (P4) and
    lifecycle state (P6) extend this the same way: add a `kind -> handler`
    entry, never a second source of truth."""

    last_seq: int = 0
    jobs: dict[str, JobState] = field(default_factory=dict)
    # set() exactly once, the instant a job reaches a terminal status —
    # tools that submit a job and need to wait for it (agents/tools/jobs.py)
    # await this instead of polling `jobs[job_id].status` in a loop.
    _job_done_events: dict[str, asyncio.Event] = field(default_factory=dict)

    def apply(self, e: Event) -> None:
        self.last_seq = max(self.last_seq, e.seq)
        handler = getattr(self, f"_on_{e.kind.replace('.', '_')}", None)
        if handler is not None:
            handler(e)

    def job_done_event(self, job_id: str) -> asyncio.Event:
        return self._job_done_events.setdefault(job_id, asyncio.Event())

    def _on_job_metric(self, e: Event) -> None:
        job_id = e.payload["job_id"]
        job = self.jobs.setdefault(job_id, JobState(job_id=job_id, project=e.project))
        job.metrics.setdefault(e.payload["k"], []).append((e.payload["step"], e.payload["v"]))

    def _on_job_log(self, e: Event) -> None:
        job_id = e.payload["job_id"]
        self.jobs.setdefault(job_id, JobState(job_id=job_id, project=e.project))

    def _on_job_done(self, e: Event) -> None:
        job_id = e.payload["job_id"]
        job = self.jobs.setdefault(job_id, JobState(job_id=job_id, project=e.project))
        job.status = e.payload["status"]
        job.final = e.payload.get("final")
        job.error_sig = e.payload.get("error_sig")
        self.job_done_event(job_id).set()
