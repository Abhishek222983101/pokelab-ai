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
from pokelab_brain.oak.whatif import WhatIfRun
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

# Evolution lines (§2.4), same as web/lib/roster.ts: promoting an agent = its next species.
LINES: dict[str, list[str]] = {
    "pichu": ["pichu", "pikachu", "raichu"], "pikachu": ["pichu", "pikachu", "raichu"], "raichu": ["pichu", "pikachu", "raichu"],
    "charmander": ["charmander", "charmeleon", "charizard"], "charmeleon": ["charmander", "charmeleon", "charizard"],
    "bulbasaur": ["bulbasaur", "ivysaur", "venusaur"], "ivysaur": ["bulbasaur", "ivysaur", "venusaur"],
    "squirtle": ["squirtle", "wartortle", "blastoise"], "wartortle": ["squirtle", "wartortle", "blastoise"],
    "abra": ["abra", "kadabra", "alakazam"], "kadabra": ["abra", "kadabra", "alakazam"],
    "porygon": ["porygon", "porygon2"], "magnemite": ["magnemite", "magneton"],
    "hoothoot": ["hoothoot", "noctowl"], "zubat": ["zubat", "golbat", "crobat"], "golbat": ["zubat", "golbat", "crobat"],
}
# Promotion rule (rule-based; the designed shadow-evaluation gate is NOT implemented): an agent evolves once
# it has EVOLVE_MIN_REWARDS rewarded tasks since it last evolved with a mean reward >= EVOLVE_MIN_MEAN.
EVOLVE_MIN_REWARDS = int(os.environ.get("POKELAB_EVOLVE_MIN_REWARDS", "8"))  # shown in every agent.evolved event
EVOLVE_MIN_MEAN = 0.90

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
                # a project still "running" at boot was cut off by a restart: close it explicitly instead of
                # leaving a ghost quest that never finishes
                for pid, proj in list(self.state.projects.items()):
                    if proj.get("status") == "running":
                        await self.publish("project.abandoned", {"project_id": pid, "reason": "the brain restarted before this project finished"}, project=pid)
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

    async def maybe_evolve(self) -> None:
        for aid, a in list(self.state.agents.items()):
            if a.get("status") != "active":
                continue
            line = LINES.get(a.get("species", ""))
            if not line or line.index(a["species"]) + 1 >= len(line):
                continue
            rewards = [r for who, r in self.state.rewards if who == aid][int(a.get("evolved_at_rewards", 0)):]
            if len(rewards) < EVOLVE_MIN_REWARDS:
                continue
            mean = sum(rewards) / len(rewards)
            if mean < EVOLVE_MIN_MEAN:
                continue
            nxt = line[line.index(a["species"]) + 1]
            await self.publish("agent.evolved", {
                "agent_id": aid, "from_species": a["species"], "species": nxt, "version": int(a.get("version", 1)) + 1,
                "evidence": {"n": len(rewards), "mean_reward": round(mean, 4)},
                "rule": f">= {EVOLVE_MIN_REWARDS} rewarded tasks with mean reward >= {EVOLVE_MIN_MEAN} (rule-based promotion)",
            })

    # ------------------------------------------------------------------ one project
    async def reset_team(self, seq: int) -> None:
        """Demo reset: every evolved agent returns to its base species/version (an agent.devolved event
        each, with the reason) and its evolution counter restarts from its current reward count."""
        base = {m["agent_id"]: m for m in BASE_TEAM}
        n = 0
        for aid, a in list(self.state.agents.items()):
            b = base.get(aid)
            if b is None or (a.get("species") == b["species"] and int(a.get("version", 1)) == b["version"]):
                continue
            await self.publish("agent.devolved", {
                "agent_id": aid, "from_species": a.get("species"), "species": b["species"], "version": b["version"],
                "reason": "demo reset requested by the researcher (rewards history is kept)",
            })
            n += 1
        await self.publish("project.rejected", {"request_seq": seq, "text": "reset team", "command": "reset", "reason": f"team reset: {n} agent(s) returned to their base species"})

    async def handle_whatif(self, seq: int, text: str) -> None:
        profile = KITS["grokking"]
        project_id = f"p-whatif-{uuid.uuid4().hex[:6]}"
        self._rebuild_from_log()
        run = WhatIfRun(project_id=project_id, profile=profile, tool_ctx=ToolContext(bus=self.bus, state=self.state, project=project_id, timeout_s=150))
        steps, step_configs = run.plan()
        await self.publish("project.created", {
            "project_id": project_id, "request_seq": seq, "text": text, "kind": "whatif", "paper": "grokking", "kit": profile.kit,
            "title": "What if? Weight decay x data fraction (Grokking)", "claim": {"metric": profile.final_key, "value": profile.claim},
            "plan": [{"step_id": s.id, "capability": s.cap, "title": s.title, "after": s.after} for s in steps],
        }, project=project_id)
        active = {aid: a.capabilities for aid, a in self.roster.items() if a.status == "active"}
        result = await run_plan(
            steps, active, self.selector, step_configs, emit=lambda k, p: self.publish(k, p, project=project_id),
            project_id=project_id, executors=run.executors(), max_parallel=1,
            narrate=run.narrate, dwell_s=float(os.environ.get("POKELAB_STEP_DWELL_S", "2.5")),
        )
        grokked = sum(1 for c in run.cells if c["claim_hit_step"] is not None)
        await self.publish("project.completed", {
            "project_id": project_id, "paper": "grokking", "kit": profile.kit, "verdict": "WHAT-IF COMPLETE",
            "metric": "settings that grokked", "value": float(grokked), "claim": float(len(run.cells)), "job_id": None,
            "report": str(run.workdir / "report.md"), "steps": {"completed": result.completed, "failed": result.failed, "escalated": result.escalated},
        }, project=project_id)
        await self.maybe_evolve()

    async def handle_request(self, seq: int, text: str) -> None:
        if any(w in text.lower() for w in ("reset team", "de-evolve", "devolve")):
            await self.reset_team(seq)
            return
        if any(w in text.lower() for w in ("what if", "what-if", "whatif", "explore", "safari")):
            await self.handle_whatif(seq, text)
            return
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
        await self.maybe_evolve()
        if run.verdict == "REPRODUCED":
            await self.publish("project.badge_awarded", {
                "project_id": project_id, "paper": paper, "kit": profile.kit, "value": run.value, "claim": profile.claim,
                "job_id": full.get("job_id"),
            }, project=project_id)
