"""Professor Oak's live loop (§6.2): the part of the brain that turns a researcher's request into a
real project — team, plan, real jobs, real verdict — and publishes every step as events the game
and console render. Everything it knows is rebuilt from the event log on start (a restart loses
nothing), and it only acts on requests nobody has handled yet.

  project.requested ─► intake (paper words, else LLM) ─► project.created (+ plan)
     ─► run_plan (Selector picks agents · real executors · lifecycle spawn/retire)
        └─ agent.task_started / task_finished|failed / rewarded  (scheduler emit)
     ─► project.completed {verdict, value, claim, job_id, report} ─► project.badge_awarded (REPRODUCED)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any

from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.agents.tools.jobs import ToolContext
from pokelab_brain.bus import BrainBus
from pokelab_brain.oak.executors import ProjectRun, narrate_step, specialize_checks
from pokelab_brain.oak.kits import KITS, paper_for
from pokelab_brain.oak.lifecycle_loop import LifecycleLoop
from pokelab_brain.oak.planner import load_template, validate_plan
from pokelab_brain.oak.scheduler import run_plan
from pokelab_brain.state import StateProjection
from pokelab_labml.selector.thompson import ThompsonSelector

logger = logging.getLogger(__name__)

# §2.4 base roster: role, species line, capabilities. Pikachu is seeded at v2 — it really was
# refined once during the build (logged history), the rest start at v1.
BASE_TEAM: list[dict[str, Any]] = [
    {"agent_id": "pikachu", "species": "pikachu", "role": "Paper Reader", "version": 2,
     "capabilities": ["paper_read", "spec_extract", "claim_extract"]},
    {"agent_id": "charmander", "species": "charmander", "role": "Implementer", "version": 1,
     "capabilities": ["implement", "code_edit"]},
    {"agent_id": "bulbasaur", "species": "bulbasaur", "role": "Environment Engineer", "version": 1,
     "capabilities": ["env_setup", "dependency_fix", "data_prep"]},
    {"agent_id": "squirtle", "species": "squirtle", "role": "Debugger", "version": 1,
     "capabilities": ["debug", "repair"]},
    {"agent_id": "abra", "species": "abra", "role": "Analyst", "version": 1,
     "capabilities": ["analyze", "repro_compare", "explain"]},
    {"agent_id": "porygon", "species": "porygon", "role": "Experimenter", "version": 1,
     "capabilities": ["run_experiment", "experiment_design", "whatif_design"]},
    {"agent_id": "magnemite", "species": "magnemite", "role": "Compute Runner", "version": 1,
     "capabilities": ["compute_ops", "remote_run"]},
    {"agent_id": "hoothoot", "species": "hoothoot", "role": "Scribe", "version": 1,
     "capabilities": ["report_write", "notes", "author_email"]},
    {"agent_id": "zubat", "species": "zubat", "role": "Scout", "version": 1,
     "capabilities": ["literature_search", "paper_discover"]},
]

IDLE_BEFORE_ACTING_S = 0.6  # wait for the replay burst to settle before acting on "pending" work


class OakRuntime:
    def __init__(self, bus: BrainBus, state: StateProjection, llm: tuple[Any, list[str]] | None = None):
        self.bus = bus
        self.state = state
        self.router, self.route = llm if llm else (None, [])
        self.selector = ThompsonSelector()
        self.roster: dict[str, AgentSpec] = {}
        self.lifecycle: LifecycleLoop | None = None
        self.last_event_at = time.monotonic()
        self._busy = False
        self._req = 0

    # ------------------------------------------------------------------ events
    def saw_event(self) -> None:
        self.last_event_at = time.monotonic()

    async def publish(self, kind: str, payload: dict[str, Any], project: str | None = None) -> None:
        self._req += 1
        await self.bus.publish([{
            "kind": kind, "v": 1, "project": project, "actor": "oak", "corr": None, "causation": None,
            "payload": payload, "display": None,
        }], req=f"oak-{self._req}")

    # ------------------------------------------------------------------ team
    def _rebuild_from_log(self) -> None:
        """Roster and Selector posteriors exactly as the event log says (§6.12)."""
        self.roster = {
            aid: AgentSpec(id=aid, species=a.get("species", aid), role=a.get("role", "agent"),
                           capabilities=list(a.get("capabilities") or [a.get("capability")]),
                           prompt_ref="generalist.md", status=a.get("status", "active"),
                           generation=int(a.get("version", 1)) - 1)
            for aid, a in self.state.agents.items()
        }
        self.selector = ThompsonSelector()
        for aid, reward in self.state.rewards:
            self.selector.record_outcome(aid, reward)
        if self.router is not None:
            self.lifecycle = LifecycleLoop(
                roster=self.roster, selector=self.selector, router=self.router, route=self.route,
                publish=lambda kind, payload: self.publish(kind, payload),
            )

    async def ensure_team(self) -> None:
        if self.state.agents:
            return
        for member in BASE_TEAM:
            await self.publish("agent.spawned", {**member, "reason": "base roster (§2.4)", "capability": member["capabilities"][0]})

    # ------------------------------------------------------------------ main loop
    async def run_forever(self) -> None:
        team_checked = False
        while True:
            await asyncio.sleep(0.25)
            if time.monotonic() - self.last_event_at < IDLE_BEFORE_ACTING_S or self._busy:
                continue
            if not team_checked:
                await self.ensure_team()
                team_checked = True
                continue
            pending = self.state.pending_requests()
            if pending:
                seq, text = pending[0]
                self.state.handled_requests.add(seq)  # claim it locally before the event round-trips
                self._busy = True
                try:
                    await self.handle_request(seq, text)
                except Exception:  # noqa: BLE001 - a failed project must never take Oak down
                    logger.exception("project for request %s failed", seq)
                    await self.publish("project.rejected", {"request_seq": seq, "reason": "internal error, see brain log"})
                finally:
                    self._busy = False

    # ------------------------------------------------------------------ one project
    async def handle_request(self, seq: int, text: str) -> None:
        paper = paper_for(text)
        if paper is None and self.router is not None:
            from pokelab_brain.oak.intake import intake
            spec = await asyncio.to_thread(intake, text, self.router, self.route)
            paper = next((p for p in spec.papers if p in KITS), None) or next((paper_for(p) for p in spec.papers if paper_for(p)), None)
        if paper is None:
            await self.publish("project.rejected", {
                "request_seq": seq, "text": text,
                "reason": "no paper pack matches this request yet (known: " + ", ".join(sorted(KITS)) + ")",
            })
            return

        profile = KITS[paper]
        project_id = f"p-{paper}-{uuid.uuid4().hex[:6]}"
        steps_raw = load_template("reproduce")
        self._rebuild_from_log()
        known_caps = {c for a in self.roster.values() for c in a.capabilities} | {s["cap"] for s in steps_raw}
        steps, errors = validate_plan(steps_raw, known_caps, {})
        assert not errors, errors
        steps = specialize_checks(steps, profile)

        await self.publish("project.created", {
            "project_id": project_id, "request_seq": seq, "text": text, "kind": "reproduce", "paper": paper,
            "kit": profile.kit, "title": f"Reproduce {paper}",
            "claim": {"metric": profile.final_key, "value": profile.claim},
            "plan": [{"step_id": s.id, "capability": s.cap, "title": s.title, "after": s.after} for s in steps],
        }, project=project_id)

        run = ProjectRun(project_id=project_id, profile=profile,
                         tool_ctx=ToolContext(bus=self.bus, state=self.state, project=project_id, timeout_s=150))
        active = {aid: a.capabilities for aid, a in self.roster.items() if a.status == "active"}
        step_configs = {s.id: {"kit": profile.kit} for s in steps if s.cap == "run_experiment"}
        result = await run_plan(
            steps, active, self.selector, step_configs, emit=lambda k, p: self.publish(k, p, project=project_id),
            project_id=project_id, executors=run.executors(), max_parallel=1,
            narrate=lambda st, c, r: narrate_step(run, st, c, r),
            dwell_s=float(os.environ.get("POKELAB_STEP_DWELL_S", "2.5")),
            on_capability_gap=self.lifecycle.on_capability_gap if self.lifecycle else None,
            on_task_outcome=self.lifecycle.on_task_outcome if self.lifecycle else None,
        )

        full = run.full_result or {}
        await self.publish("project.completed", {
            "project_id": project_id, "paper": paper, "kit": profile.kit,
            "verdict": run.verdict or "FAILED", "metric": profile.final_key, "value": run.value, "claim": profile.claim,
            "job_id": full.get("job_id"), "report": str(run.workdir / "report.md"),
            "steps": {"completed": result.completed, "failed": result.failed, "escalated": result.escalated},
        }, project=project_id)
        if run.verdict == "REPRODUCED":
            await self.publish("project.badge_awarded", {
                "project_id": project_id, "paper": paper, "kit": profile.kit, "value": run.value, "claim": profile.claim,
                "job_id": full.get("job_id"),
            }, project=project_id)
