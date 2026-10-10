"""Kaggle runner (§10.2): pushes a kernel via the real `kaggle` CLI,
polls until it finishes, and parses its logs for our JSON-lines
protocol. [MEASURED, earlier session]: push -> finish is ~40s round
trip on a fresh kernel slug; `kernels status` polling and `kernels
output` to retrieve logs are both real CLI calls, no API client needed.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KaggleRunResult:
    status: str  # "complete" | "error" | "timeout"
    protocol_lines: list[dict] = field(default_factory=list)
    raw_log: str = ""


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def push_and_run(
    kernel_dir: str | Path,
    slug: str,
    username: str,
    script_name: str,
    accelerator: str | None = "NvidiaTeslaT4",
    poll_interval_s: float = 5.0,
    timeout_s: float = 300.0,
) -> KaggleRunResult:
    """`kernel_dir` must contain `script_name` (the kernel's actual code)
    — this writes `kernel-metadata.json` into it, matching what `kaggle
    kernels push` expects, then pushes, polls, and pulls the log."""
    kernel_dir = Path(kernel_dir)
    metadata = {
        "id": f"{username}/{slug}",
        "title": slug,
        "code_file": script_name,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": accelerator is not None,
        "enable_internet": True,
    }
    (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))

    push_cmd = ["kaggle", "kernels", "push", "-p", str(kernel_dir)]
    push = _run(push_cmd, timeout=60)
    if push.returncode != 0:
        return KaggleRunResult(status="error", raw_log=push.stderr)

    deadline = time.monotonic() + timeout_s
    ref = f"{username}/{slug}"
    status = "running"
    while time.monotonic() < deadline:
        status_proc = _run(["kaggle", "kernels", "status", ref], timeout=30)
        output = status_proc.stdout.strip()
        if "complete" in output.lower():
            status = "complete"
            break
        if "error" in output.lower() or "cancelled" in output.lower():
            status = "error"
            break
        time.sleep(poll_interval_s)
    else:
        status = "timeout"

    log_proc = _run(["kaggle", "kernels", "output", ref, "-p", str(kernel_dir / "_output")], timeout=60)
    raw_log = log_proc.stdout + log_proc.stderr

    lines = _extract_protocol_lines(kernel_dir / "_output" / f"{slug}.log")

    return KaggleRunResult(status=status, protocol_lines=lines, raw_log=raw_log)


def _extract_protocol_lines(log_file: str | Path) -> list[dict]:
    log_file = Path(log_file)
    """Kaggle's kernel log is NOT raw stdout — it's its own JSON array of
    `{"stream_name", "time", "data"}` entries, where `data` holds one
    chunk of the real stdout/stderr (with its own trailing newline).
    [BUG FOUND via a real kernel run: the log looked like JSON lines at a
    glance but wasn't — had to actually `cat` the downloaded file to see
    the wrapper format.] We take every stdout entry's `data`, split it on
    newlines (a chunk can contain more than one print), and parse each
    resulting line as our protocol."""
    if not log_file.exists():
        return []
    try:
        entries = json.loads(log_file.read_text())
    except json.JSONDecodeError:
        return []

    lines = []
    for entry in entries:
        if entry.get("stream_name") != "stdout":
            continue
        for raw in entry.get("data", "").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "t" in parsed:
                lines.append(parsed)
    return lines
