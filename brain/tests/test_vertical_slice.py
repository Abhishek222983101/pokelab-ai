"""P4.10 — THE vertical slice: Oak hands an agent the grokking paper, the
agent (a real small LLM over Groq) uses the real action protocol to call
run_kit, which submits a REAL GPU job through a REAL labd + warm pool; the
agent reads back the real result and writes a <final> report; the
comparator checks it against the curated paper claim.

Nothing here is mocked. This is the single test that proves every layer
built so far (labd, the warm pool, the WS hub, the brain bus, the LLM
router, the protocol parser, the tool, reward/comparator) works together.
"""
import asyncio
import os
import socket
import subprocess
import time

import pytest

from pokelab_brain.agents.protocol import parse_response
from pokelab_brain.agents.runtime import run_agent
from pokelab_brain.agents.spec import load_prompt, render_prompt
from pokelab_brain.agents.tools.jobs import TOOL_DESCRIPTION, TOOL_NAME, ToolContext, run_kit
from pokelab_brain.bus import BrainBus
from pokelab_brain.llm.providers import GroqProvider
from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.papers.packs import get_pack
from pokelab_brain.science.comparator import compare
from pokelab_brain.state import StateProjection

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABD_BIN = os.path.join(ROOT, "core", "target", "debug", "labd")
WORKERS_PYTHON = os.path.join(ROOT, "workers", ".venv", "bin", "python")
WORKERS_CWD = os.path.join(ROOT, "workers")
PROMPTS_DIR = os.path.join(ROOT, "brain", "pokelab_brain", "agents", "prompts")


def _load_env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"labd never opened port {port}")


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
@pytest.mark.skipif(not os.path.exists(LABD_BIN), reason="labd not built")
@pytest.mark.skipif(not os.path.exists(WORKERS_PYTHON), reason="workers/.venv not found")
def test_full_vertical_slice_reproduces_grokking(tmp_path):
    port = _free_port()
    secret = "vslice-secret"
    env = {
        **os.environ,
        "LABD_PORT": str(port),
        "LABD_DB_PATH": str(tmp_path / "lab.db"),
        "LABD_BRAIN_SECRET": secret,
        "LABD_PAIRING_SECRET": "p",
        "LABD_WORKERS_PYTHON": WORKERS_PYTHON,
        "LABD_WORKERS_CWD": WORKERS_CWD,
        "LABD_POOL_SIZE": "1",
        "LABD_WORKER_DEVICE": "cuda",
    }
    proc = subprocess.Popen([LABD_BIN], cwd=os.path.join(ROOT, "core"), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_for_port(port)

        async def drive():
            bus = BrainBus(f"ws://127.0.0.1:{port}/internal/brain", secret)
            await bus.connect()
            state = StateProjection()

            async def pump_state():
                async for event in bus.subscribe(since=0):
                    state.apply(event)

            pump_task = asyncio.create_task(pump_state())

            router = LlmRouter(
                providers={"groq": GroqProvider(GROQ_KEY)},
                cache_db=tmp_path / "llm_cache.db",
                budget_db=tmp_path / "brain.db",
            )
            tool_ctx = ToolContext(bus=bus, state=state, project="grokking-demo", timeout_s=60.0)

            task_text = (
                "Reproduce the grokking paper's modular-addition result. "
                'Call run_kit with EXACTLY this JSON for args: '
                '{"kit": "grokking", "config": {"model": "transformer", "p": 113, '
                '"frac": 0.5, "steps": 20000, "eval_every": 200, "device": "cuda", '
                '"stop_at": 0.95}}. '
                "Wait for the tool result, then reply with <final> containing "
                '{"summary": "...", "result": {"test_acc": <the test_acc you were given>}}.'
            )
            prompt_template = load_prompt(PROMPTS_DIR, "generalist.md")
            system_prompt = render_prompt(prompt_template, TOOL_DESCRIPTION, task_text)

            try:
                result = await run_agent(
                    router=router,
                    route=["groq"],
                    system_prompt=system_prompt,
                    tools={TOOL_NAME: run_kit},
                    tool_ctx=tool_ctx,
                    max_turns=5,
                    model="qwen/qwen3.8-27b",
                    max_tokens=600,
                    reasoning_effort="low",
                )
            finally:
                pump_task.cancel()
                try:
                    await pump_task
                except asyncio.CancelledError:
                    pass
                router.close()
                await bus.close()

            return result

        result = asyncio.run(drive())

        assert not result.gave_up, f"agent gave up; turns={result.turns}"
        assert result.final is not None, f"agent never reached <final>; turns={result.turns}"

        # the agent must have actually called run_kit (not hallucinated a result)
        tool_turns = [t for t in result.turns if t.action_tool == TOOL_NAME]
        assert tool_turns, f"agent never called run_kit; turns={result.turns}"
        tool_result = tool_turns[-1].tool_result
        assert tool_result["status"] == "ok", f"job did not succeed: {tool_result}"
        for t in result.turns:
            print("TURN:", t.action_tool, t.action_args, "malformed=", t.malformed)
        print("TOOL RESULT:", tool_result)
        assert tool_result["final"]["test_acc"] >= 0.95, f"did not grok: {tool_result['final']}"

        pack = get_pack("grokking")
        report = compare(result.final.get("result", {}), "test_acc", pack)
        print(f"\nVERTICAL SLICE REPORT: {report.narrative}")
        assert report.matched, report.narrative

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
