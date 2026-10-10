"""The stdin/stdout JSON-lines protocol between labd (parent) and a warm
worker (this process). See docs §5.5.3 / §5.5.5.

Every line labd sends on stdin is a command: {"t": "job", ...} or
{"t": "stop", ...}. Every line this process prints on stdout is one of:
    {"t": "ready", "torch": bool, "device": str, "pid": int}
    {"t": "metric", "job_id": str, "step": int, "k": str, "v": float|None}
    {"t": "log", "job_id": str, "msg": str}
    {"t": "done", "job_id": str, "status": "ok"|"stopped"|"error",
     "final": dict, "error_sig": str|None}

A line > 256 KB is never emitted (callers should keep `v`/`msg` small);
NaN/Inf floats are sent as `null` per §5.5.5 so the line stays valid JSON.
"""
from __future__ import annotations

import json
import math
import sys
from typing import Any

MAX_LINE_BYTES = 256 * 1024


def _safe_float(v: float | None) -> float | None:
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _emit(obj: dict[str, Any]) -> None:
    line = json.dumps(obj, separators=(",", ":"))
    if len(line.encode("utf-8")) > MAX_LINE_BYTES:
        # never let a bad payload wedge the pipe — log a short notice instead
        line = json.dumps({"t": "log", "msg": f"dropped oversized {obj.get('t')} line"})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def emit_ready(torch_available: bool, device: str, pid: int) -> None:
    _emit({"t": "ready", "torch": torch_available, "device": device, "pid": pid})


def emit_metric(job_id: str, step: int, key: str, value: float | None) -> None:
    _emit({"t": "metric", "job_id": job_id, "step": step, "k": key, "v": _safe_float(value)})


def emit_log(job_id: str, msg: str) -> None:
    _emit({"t": "log", "job_id": job_id, "msg": msg[:2000]})


def emit_done(
    job_id: str,
    status: str,
    final: dict[str, Any] | None = None,
    error_sig: str | None = None,
) -> None:
    _emit({
        "t": "done",
        "job_id": job_id,
        "status": status,
        "final": final or {},
        "error_sig": error_sig,
    })


def read_commands():
    """Yield parsed stdin commands, one dict per line, for the lifetime of
    the process. Malformed lines are logged and skipped (never crash the
    worker on a bad line — §5.5.5 applies both directions)."""
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            emit_log("-", f"worker received non-JSON stdin line, ignored: {raw[:200]}")
