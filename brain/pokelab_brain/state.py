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
    # the team, as the event log says it is (agent.spawned / agent.retired)
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    # every agent.rewarded, in order — the Selector's posteriors are rebuilt from these on restart
    rewards: list[tuple[str, float]] = field(default_factory=list)
    # project.requested seq -> text; a request is "pending" until a project.created cites its seq
    requests: dict[int, str] = field(default_factory=dict)
    projects: dict[str, dict[str, Any]] = field(default_factory=dict)
    handled_requests: set[int] = field(default_factory=set)

    def apply(self, e: Event) -> None:
        self.last_seq = max(self.last_seq, e.seq)
        handler = getattr(self, f"_on_{e.kind.replace('.', '_')}", None)
        if handler is not None:
            handler(e)

    def job_done_event(self, job_id: str) -> asyncio.Event:
        return self._job_done_events.setdefault(job_id, asyncio.Event())

    def pending_requests(self) -> list[tuple[int, str]]:
        return sorted((seq, text) for seq, text in self.requests.items() if seq not in self.handled_requests)

    def _on_agent_spawned(self, e: Event) -> None:
        p = e.payload
        self.agents[p["agent_id"]] = {**p, "status": "active", "spawned_seq": e.seq}

    def _on_agent_retired(self, e: Event) -> None:
        a = self.agents.get(e.payload["agent_id"])
        if a is not None:
            a["status"] = "retired"

    def _on_agent_rewarded(self, e: Event) -> None:
        self.rewards.append((e.payload["agent_id"], float(e.payload["reward"])))

    def _on_project_requested(self, e: Event) -> None:
        self.requests[e.seq] = e.payload.get("text", "")

    def _on_project_created(self, e: Event) -> None:
        self.projects[e.payload["project_id"]] = {**e.payload, "status": "running"}
        if (req := e.payload.get("request_seq")) is not None:
            self.handled_requests.add(int(req))

    def _on_project_rejected(self, e: Event) -> None:
        if (req := e.payload.get("request_seq")) is not None:
            self.handled_requests.add(int(req))

    def _on_project_completed(self, e: Event) -> None:
        proj = self.projects.setdefault(e.payload["project_id"], {"project_id": e.payload["project_id"]})
        proj.update({**e.payload, "status": "completed"})

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
