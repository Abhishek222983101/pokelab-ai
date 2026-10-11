"""The worker protocol (§5.5.3/§5.5.5) — what pool_main.py emits and
lab-jobs' WarmPool parses. This is the one contract that's identical
character-for-character in Python (pokelab_workers.protocol) and Rust
(lab_jobs::ProtocolLine); this module exists so a THIRD consumer (a
test, a doc, a future language) has one place to check the shape
against instead of two.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ReadyLine(BaseModel):
    t: Literal["ready"] = "ready"
    torch: bool
    device: str
    pid: int


class MetricLine(BaseModel):
    t: Literal["metric"] = "metric"
    job_id: str
    step: int
    k: str
    v: float | None


class LogLine(BaseModel):
    t: Literal["log"] = "log"
    job_id: str
    msg: str


class DoneLine(BaseModel):
    t: Literal["done"] = "done"
    job_id: str
    status: Literal["ok", "stopped", "error", "timeout"]
    final: dict[str, Any] = {}
    error_sig: str | None = None


class JobCommand(BaseModel):
    """What labd writes to a worker's stdin to assign work."""
    t: Literal["job"] = "job"
    job_id: str
    kit: str
    config: dict[str, Any]


class StopCommand(BaseModel):
    t: Literal["stop"] = "stop"
    job_id: str
    reason: str = ""
