"""The "what if?" project (PS03 D14/D23/D13/D24, the Safari map): Oak designs a small grid over the grokking
kit's two real knobs — weight decay x training-data fraction — runs every cell as a REAL training job on the
GPU, and explains from the measured curves where (and how much later) grokking happens or stops.

Every number comes from a job's own metrics; the "explanation" lines are computed (comparisons of measured
steps), not model-written text. Cells stream to the UI as `explore.cell` events, so the Safari map fills in
tile by tile as real runs finish.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pokelab_brain.agents.tools.jobs import ToolContext, run_kit
from pokelab_brain.oak.kits import KitProfile
from pokelab_brain.oak.planner import PlanStep

PROJECTS_DIR = Path(__file__).resolve().parents[3] / "var" / "projects"
GRID_WD = [0.0, 0.3, 1.0]
GRID_FRAC = [0.3, 0.5]
MAX_STEPS = 3000


def _fmt(v: Any) -> str:
    return f"{v:.3f}" if isinstance(v, float) else str(v)


@dataclass
class WhatIfRun:
    project_id: str
    profile: KitProfile
    tool_ctx: ToolContext
    cells: list[dict[str, Any]] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    workdir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.workdir = PROJECTS_DIR / self.project_id
        self.workdir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ plan
    def plan(self) -> tuple[list[PlanStep], dict[str, dict[str, Any]]]:
        steps = [PlanStep(id="s1", cap="whatif_design", title="Design the weight-decay x data-fraction grid", accept=["metric_present:cells"])]
        configs: dict[str, dict[str, Any]] = {}
        i = 2
        for wd in GRID_WD:
            for frac in GRID_FRAC:
                sid = f"s{i}"
                steps.append(PlanStep(id=sid, cap="run_experiment", title=f"Run wd={wd} frac={frac}", accept=["job_completed:cell"], after=["s1"]))
                configs[sid] = {"wd": wd, "frac": frac}
                i += 1
        run_ids = [s.id for s in steps if s.cap == "run_experiment"]
        steps.append(PlanStep(id=f"s{i}", cap="analyze", title="Compare the cells and explain the differences", accept=["metric_present:grokked"], after=run_ids))
        steps.append(PlanStep(id=f"s{i + 1}", cap="report_write", title="Write the what-if report", accept=[], after=[f"s{i}"]))
        return steps, configs

    def executors(self) -> dict[str, Any]:
        return {"whatif_design": self.design, "run_experiment": self.run_cell, "analyze": self.analyze, "report_write": self.report}

    # ------------------------------------------------------------------ steps
    async def design(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        cells = [{"wd": wd, "frac": frac} for wd in GRID_WD for frac in GRID_FRAC]
        return {"status": "ok", "final": {"cells": len(cells)}, "events": [("explore.planned", {
            "title": "Grokking: weight decay x training-data fraction", "metric": "test_acc", "claim": self.profile.claim,
            "axes": {"wd": GRID_WD, "frac": GRID_FRAC}, "cells": cells, "max_steps": MAX_STEPS})]}

    async def run_cell(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        wd, frac = cfg["wd"], cfg["frac"]
        config = {**self.profile.full, "wd": wd, "frac": frac, "steps": MAX_STEPS}
        r = await run_kit({"kit": self.profile.kit, "config": config}, self.tool_ctx)
        final = r.get("final") or {}
        job = self.tool_ctx.state.jobs.get(r.get("job_id") or "")
        test = [(st, v) for st, v in (job.metrics.get("test_acc", []) if job else []) if v is not None]
        train = [(st, v) for st, v in (job.metrics.get("train_acc", []) if job else []) if v is not None]
        hit = next((st for st, v in test if v >= self.profile.claim), None)
        sat = next((st for st, v in train if v >= 0.99), None)
        cell = {"wd": wd, "frac": frac, "job_id": r.get("job_id"), "status": r.get("status"),
                "test_acc": final.get("test_acc"), "train_acc": final.get("train_acc"), "claim_hit_step": hit,
                "train_saturated_step": sat, "points": len(test), "wall_s": final.get("wall_s")}
        self.cells.append(cell)
        return {**r, "jobs": {"cell": {"status": r.get("status")}}, "cell": cell, "events": [("explore.cell", cell)]}

    async def analyze(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        grokked = [c for c in self.cells if c["claim_hit_step"] is not None]
        lines: list[str] = [f"{len(grokked)} of {len(self.cells)} settings reached test_acc >= {self.profile.claim}."]
        for wd in GRID_WD:
            row = [c for c in self.cells if c["wd"] == wd]
            ok = [c for c in row if c["claim_hit_step"] is not None]
            if not ok:
                best = max((c["test_acc"] or 0.0) for c in row) if row else 0.0
                lines.append(f"wd={wd}: never reached the claim in {MAX_STEPS} steps (best test_acc {best:.3f}).")
            else:
                lines.append(f"wd={wd}: reached the claim at step " + ", ".join(f"{c['claim_hit_step']} (frac {c['frac']})" for c in ok) + ".")
        base = next((c for c in self.cells if c["wd"] == 1.0 and c["frac"] == 0.5 and c["claim_hit_step"] is not None), None)
        for c in self.cells:
            if base and c is not base and c["claim_hit_step"] and c["wd"] == base["wd"]:
                lines.append(f"With frac={c['frac']} instead of {base['frac']}, grokking at wd={c['wd']} came {c['claim_hit_step'] / base['claim_hit_step']:.1f}x as late (step {c['claim_hit_step']} vs {base['claim_hit_step']}).")
        sat = [c for c in self.cells if c["train_saturated_step"] is not None and c["claim_hit_step"] is None]
        if sat:
            lines.append(f"{len(sat)} setting(s) memorised the training set (train_acc >= 0.99) but never generalised: that is memorisation without grokking.")
        self.lines = lines
        return {"status": "ok", "final": {"grokked": len(grokked), "total": len(self.cells)},
                "events": [("explore.analysis", {"lines": lines, "grokked": len(grokked), "total": len(self.cells)})]}

    async def report(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        rows = ["| wd | frac | job | test_acc | train_acc | step test>=claim | step train>=0.99 |", "|---|---|---|---|---|---|---|"]
        for c in self.cells:
            rows.append(f"| {c['wd']} | {c['frac']} | {c['job_id']} | {_fmt(c['test_acc'])} | {_fmt(c['train_acc'])} | {c['claim_hit_step']} | {c['train_saturated_step']} |")
        text = "\n".join([f"# What-if report: grokking, weight decay x data fraction", "", "## Findings", "", *[f"- {l}" for l in self.lines], "",
                         "## Evidence (every row is one real job)", "", *rows, "",
                         "Every number is measured by the job; the findings are comparisons of those numbers (no language model wrote them)."])
        (self.workdir / "report.md").write_text(text)
        return {"status": "ok", "report_text": text, "artifacts": {"report": str(self.workdir / "report.md")}}

    # ------------------------------------------------------------------ narration
    def narrate(self, step: PlanStep, cfg: dict[str, Any], result: dict[str, Any] | None) -> str | None:
        if step.cap == "whatif_design":
            return f"Designing a {len(GRID_WD)}x{len(GRID_FRAC)} grid: weight decay x data fraction" if result is None else f"Grid ready: {len(GRID_WD) * len(GRID_FRAC)} real runs"
        if step.cap == "run_experiment":
            if result is None:
                return f"Training grokking with wd={cfg['wd']}, frac={cfg['frac']} (max {MAX_STEPS} steps)"
            c = result.get("cell") or {}
            hit = c.get("claim_hit_step")
            return f"wd={cfg['wd']} frac={cfg['frac']}: test_acc {_fmt(c.get('test_acc'))}, " + (f"hit the claim at step {hit}" if hit is not None else "never reached the claim")
        if step.cap == "analyze":
            return "Comparing all cells against the baseline" if result is None else (self.lines[0] if self.lines else None)
        if step.cap == "report_write":
            return "Writing the what-if report from the measured cells" if result is None else f"Report written to var/projects/{self.project_id}/report.md"
        return None
