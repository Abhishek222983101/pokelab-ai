"""Colab runner (§10.2/P10.3): runs a script on a fresh, free Colab VM
via the real `colab` CLI (`colab run --gpu <variant> --timeout <s>
script.py`), parsing its stdout as the SAME JSON-lines protocol a local
warm worker speaks (see pokelab_workers.protocol) — so the caller doesn't
care whether a job ran locally or on a rented VM.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RemoteRunResult:
    returncode: int
    stdout: str
    stderr: str
    protocol_lines: list[dict] = field(default_factory=list)


def run_on_colab(
    script_path: str | Path,
    gpu: str | None = None,
    timeout_s: int = 120,
    script_args: list[str] | None = None,
) -> RemoteRunResult:
    """[MEASURED, §13 remote compute]: Colab's CLI default timeout is 30s
    — always pass one explicitly for anything that isn't trivial."""
    cmd = ["colab", "run"]
    if gpu:
        cmd += ["--gpu", gpu]
    cmd += ["--timeout", str(timeout_s), str(script_path)]
    if script_args:
        cmd += script_args

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 30)

    lines = []
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "t" in parsed:
            lines.append(parsed)

    return RemoteRunResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr, protocol_lines=lines)
