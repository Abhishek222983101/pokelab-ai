"""pool_main: the warm worker entrypoint (§5.5.3). One process per pool
slot, spawned once by labd and reused across jobs — importing torch and
initialising CUDA happens exactly once, which is the whole point.

    python -m pokelab_workers.pool_main --slot w-gpu-0 --device cuda:0

Lifecycle: import -> (optional prewarm) -> emit `ready` -> loop reading
`{"t":"job",...}` / `{"t":"stop",...}` lines from stdin, emitting
`metric`/`log`/`done` lines on stdout, forever (until stdin closes).
"""
from __future__ import annotations

import argparse
import os
import queue
import threading
import traceback

from pokelab_workers import protocol
from pokelab_workers.kits import base

# importing the kit modules registers them (base.KIT_REGISTRY)
from pokelab_workers.kits.smoke import spec as _smoke_spec  # noqa: F401
from pokelab_workers.kits.grokking import spec as _grokking_spec  # noqa: F401
from pokelab_workers.kits.materials import spec as _materials_spec  # noqa: F401
from pokelab_workers.kits.distillation import spec as _distillation_spec  # noqa: F401
from pokelab_workers.kits.nerf import spec as _nerf_spec  # noqa: F401
from pokelab_workers.kits.arena import spec as _arena_spec  # noqa: F401


def _try_import_torch():
    try:
        import torch  # noqa: F401

        return torch
    except ImportError:
        return None


class _ThreadStopToken:
    """A StopToken backed by a threading.Event, set by the stdin reader
    thread when a `{"t":"stop"}` line arrives for this job."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self) -> None:
        self._event.set()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--prewarm-kit", default=None, help="kit name to run once, silently, before `ready`")
    args = parser.parse_args()

    torch = _try_import_torch()
    device = args.device if torch is not None else "cpu"

    if args.prewarm_kit:
        try:
            kit = base.get_kit(args.prewarm_kit)
            kit.run(base.KitContext(
                job_id="__prewarm__",
                config={"n_steps": 5},
                emit=lambda *_: None,
                stop=base.SimpleStopToken(),
            ))
        except Exception:
            # prewarm failures should never stop the worker from going ready
            pass

    protocol.emit_ready(torch_available=torch is not None, device=device, pid=os.getpid())

    # [BUG FOUND reasoning through P10.4's kill-job UI, fixed here]: the
    # old version read stdin and ran jobs on the SAME thread. While
    # _run_job() was blocked inside a kit's training loop, the process
    # never returned to `for cmd in read_commands()` — so a `{"t":"stop"}`
    # line sent mid-job just sat unread in the pipe until the job finished
    # on its own, making "kill a running job" silently a no-op in
    # practice. Fixed with a dedicated reader thread: job commands queue
    # up for the main thread (jobs still run one at a time per slot,
    # unchanged); stop commands are applied IMMEDIATELY by the reader
    # thread itself, via a lock-protected dict, regardless of what the
    # main thread is doing.
    active_stops: dict[str, _ThreadStopToken] = {}
    stops_lock = threading.Lock()
    job_queue: queue.Queue = queue.Queue()

    def reader_loop() -> None:
        for cmd in protocol.read_commands():
            t = cmd.get("t")
            if t == "job":
                job_queue.put(cmd)
            elif t == "stop":
                job_id = cmd.get("job_id")
                with stops_lock:
                    tok = active_stops.get(job_id)
                if tok is not None:
                    tok.set()
            else:
                protocol.emit_log("-", f"unknown command type {t!r}, ignored")
        job_queue.put(None)  # stdin closed -> let the main thread exit too

    threading.Thread(target=reader_loop, daemon=True).start()

    while True:
        cmd = job_queue.get()
        if cmd is None:
            break
        job_id = cmd["job_id"]
        kit_name = cmd["kit"]
        config = cmd.get("config", {})
        stop_token = _ThreadStopToken()
        with stops_lock:
            active_stops[job_id] = stop_token
        _run_job(job_id, kit_name, config, stop_token)
        with stops_lock:
            active_stops.pop(job_id, None)


def _run_job(job_id: str, kit_name: str, config: dict, stop_token: _ThreadStopToken) -> None:
    try:
        kit = base.get_kit(kit_name)
    except KeyError as e:
        protocol.emit_done(job_id, status="error", error_sig=f"unknown_kit:{e}")
        return

    def emit(step: int, key: str, value):
        protocol.emit_metric(job_id, step, key, value)

    ctx = base.KitContext(job_id=job_id, config=config, emit=emit, stop=stop_token)
    try:
        final = kit.run(ctx)
        status = "stopped" if stop_token.is_set() else "ok"
        protocol.emit_done(job_id, status=status, final=final)
    except Exception as e:  # a kit bug must fail the job, never kill the slot
        sig = f"{type(e).__name__}:{e}"
        protocol.emit_log(job_id, traceback.format_exc()[-2000:])
        protocol.emit_done(job_id, status="error", error_sig=sig)


if __name__ == "__main__":
    main()
