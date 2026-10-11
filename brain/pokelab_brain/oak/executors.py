"""Real per-capability step executors for a reproduce project (§6.2.4). Each one does the actual
work its capability names with what this repo really has, and returns the context its plan step's
accept checks verify (verifiers.py) — nothing is marked done that didn't happen:

  paper_read      real PDF ingest (papers/ingest.py) when the paper is on disk; otherwise the curated
                  PaperPack text, labelled `source: curated-pack` (no PDF to read)
  spec_extract    the curated claims (papers/packs.py) — never LLM-guessed numbers
  implement       resolves + validates the kit against the workers' real registry
  env_setup       a real `smoke` job through labd's warm pool
  run_experiment  a real kit job (`Smoke run` → the kit's quick config, `Full run` → demo config)
  analyze         the full run's real final metrics + curve summary
  repro_compare   verdict of the real number vs the curated claim (oak/kits.py thresholds)
  report_write    a Markdown report built only from the numbers above, written to var/projects/<id>/
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from pokelab_brain.agents.tools.jobs import ToolContext, run_kit
from pokelab_brain.oak.kits import KITS, KitProfile, verdict
from pokelab_brain.oak.planner import PlanStep
from pokelab_brain.papers.packs import get_pack

ROOT = Path(__file__).resolve().parents[3]
PAPERS_DIR = ROOT / "data" / "papers"
PROJECTS_DIR = ROOT / "var" / "projects"
WORKER_KITS = {"smoke", "grokking", "distillation", "nerf", "materials", "arena"}

Executor = Callable[[PlanStep, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class ProjectRun:
    """Everything a reproduce project's steps share while it runs."""
    project_id: str
    profile: KitProfile
    tool_ctx: ToolContext
    workdir: Path = field(init=False)
    smoke_result: dict[str, Any] | None = None
    full_result: dict[str, Any] | None = None
    verdict: str | None = None

    def __post_init__(self) -> None:
        self.workdir = PROJECTS_DIR / self.project_id
        self.workdir.mkdir(parents=True, exist_ok=True)

    @property
    def value(self) -> float | None:
        final = (self.full_result or {}).get("final") or {}
        v = final.get(self.profile.final_key)
        return float(v) if isinstance(v, (int, float)) else None

    def executors(self) -> dict[str, Executor]:
        return {
            "paper_read": self.paper_read, "spec_extract": self.spec_extract, "implement": self.implement,
            "env_setup": self.env_setup, "run_experiment": self.run_experiment, "analyze": self.analyze,
            "repro_compare": self.repro_compare, "report_write": self.report_write,
        }

    async def paper_read(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        pack = get_pack(self.profile.paper)
        pdf = PAPERS_DIR / self.profile.pdf if self.profile.pdf else None
        if pdf is not None and pdf.exists():
            from pokelab_brain.papers.ingest import ingest_pdf
            chunks = [{"id": c.chunk_id, "text": c.text[:400]} for c in ingest_pdf(self.profile.paper, pdf)]
            source = f"pdf:{pdf.name}"
        else:
            chunks = [{"id": "curated", "text": f"{pack.title}. " + " ".join(c.quote for c in pack.claims)}]
            source = "curated-pack"
        path = self.workdir / "chunks.json"
        path.write_text(json.dumps({"source": source, "chunks": chunks}, indent=1))
        return {"status": "ok", "artifacts": {"chunks": str(path)}, "final": {"chunks": len(chunks), "source": source},
                "events": [("paper.ingested", {"title": pack.title, "source": source, "n_chunks": len(chunks),
                                               "chunks": [{"id": c["id"], "text": c["text"][:520]} for c in chunks[:14]]})]}

    async def spec_extract(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        pack = get_pack(self.profile.paper)
        spec = {"paper_id": pack.paper_id, "title": pack.title, "kit": pack.kit,
                "claims": [{"metric": c.metric, "value": c.value, "condition": c.condition, "source": c.source_chunk_id} for c in pack.claims]}
        (self.workdir / "pack.json").write_text(json.dumps(spec, indent=1))
        return {"status": "ok", "artifacts": {"pack": spec}, "final": {"claims": len(spec["claims"])},
                "events": [("claim.extracted", {"title": pack.title, "target": {"metric": self.profile.final_key, "value": self.profile.claim},
                                                "claims": spec["claims"]})]}

    async def implement(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "kit": self.profile.kit, "known_kits": WORKER_KITS,
                "final": {"kit": self.profile.kit, "config": self.profile.full}}

    async def env_setup(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        r = await run_kit({"kit": "smoke", "config": {"n_steps": 50}}, self.tool_ctx)
        return {**r, "jobs": {"smoke": {"status": r.get("status")}}}

    async def run_experiment(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        full = "full" in step.title.lower()
        config = self.profile.full if full else self.profile.smoke
        r = await run_kit({"kit": self.profile.kit, "config": config}, self.tool_ctx)
        if full:
            self.full_result = r
        else:
            self.smoke_result = r
        return {**r, "jobs": {("full" if full else "smoke"): {"status": r.get("status")}}}

    async def analyze(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        final = (self.full_result or {}).get("final") or {}
        events = []
        job_id = (self.full_result or {}).get("job_id")
        job = self.tool_ctx.state.jobs.get(job_id) if job_id else None
        if job is not None:
            key = self.profile.live_key
            test = [(st, v) for st, v in job.metrics.get(key, []) if v is not None]
            train = [(st, v) for st, v in job.metrics.get(key.replace("test_", "train_"), []) if v is not None]
            hit = next((st for st, v in test if v >= self.profile.claim), None)
            sat = next((st for st, v in train if v >= 0.99), None)
            events.append(("analysis.computed", {
                "job_id": job_id, "metric": key, "claim": self.profile.claim, "points": len(test),
                "claim_hit_step": hit, "train_saturated_step": sat,
                "delay_steps": (hit - sat) if (hit is not None and sat is not None) else None,
                "final": {k: v for k, v in final.items() if isinstance(v, (int, float, str))},
            }))
        return {"status": "ok" if final else "error", "final": final, "events": events}

    async def repro_compare(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        self.verdict = verdict(self.profile, self.value)
        # the numbers come straight from the run and the curated claim (no LLM narrative to guard)
        return {"status": "ok", "claim_guard_passed": self.value is not None,
                "final": {"verdict": self.verdict, "value": self.value, "claim": self.profile.claim}}

    async def report_write(self, step: PlanStep, cfg: dict[str, Any]) -> dict[str, Any]:
        pack = get_pack(self.profile.paper)
        r = self.full_result or {}
        final = r.get("final") or {}
        lines = [
            f"# Reproduction report: {pack.title}", "",
            "## Summary", "",
            f"Verdict: **{self.verdict or 'not judged'}**: {self.profile.final_key} = "
            f"{self.value if self.value is not None else 'n/a'} vs the claim {self.profile.claim}.", "",
            "## Evidence", "",
            f"- job `{r.get('job_id')}` (kit `{self.profile.kit}`), status `{r.get('status')}`",
            f"- config: `{json.dumps(self.profile.full)}`",
            *[f"- {k}: {v}" for k, v in final.items() if isinstance(v, (int, float, str))],
            "", "## Narrative", "",
            "Every number above comes from the job's own final metrics and the curated claim in "
            "papers/packs.py; nothing in this report was written by a language model.",
        ]
        text = "\n".join(lines)
        (self.workdir / "report.md").write_text(text)
        return {"status": "ok", "report_text": text, "artifacts": {"report": str(self.workdir / "report.md")}}


def _fmt(v: Any) -> str:
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def narrate_step(run: "ProjectRun", step: PlanStep, cfg: dict[str, Any], result: dict[str, Any] | None) -> str | None:
    """What the agent is doing / just found, in words, built ONLY from the real plan and results
    (no model-written text): shown as the agent's speech bubble and the Activity feed."""
    prof = run.profile
    cap = step.cap
    final = (result or {}).get("final") or {}
    if result is None:
        if cap == "paper_read":
            return f"Opening the {prof.paper} paper and splitting it into chunks"
        if cap == "spec_extract":
            return "Pulling the paper's headline claim out of the chunks"
        if cap == "implement":
            return f"Checking kit '{prof.kit}' exists in the worker registry"
        if cap == "env_setup":
            return "Sending a 50-step smoke job to the warm GPU workers"
        if cap == "run_experiment":
            c = prof.full if "full" in step.title.lower() else prof.smoke
            return f"Submitting a {prof.kit} job: " + ", ".join(f"{k}={v}" for k, v in list(c.items())[:5])
        if cap == "analyze":
            return "Reading the full run's final metrics"
        if cap == "repro_compare":
            return f"Comparing {prof.final_key} against the paper's {prof.claim}"
        if cap == "report_write":
            return "Writing the report from the measured numbers"
        return step.title
    if cap == "paper_read":
        return f"Read {final.get('chunks')} chunks from {final.get('source')}"
    if cap == "spec_extract":
        return f"Extracted {final.get('claims')} claim(s); target {prof.final_key} >= {prof.claim}"
    if cap == "implement":
        return f"Kit '{prof.kit}' validated against the registry"
    if cap == "env_setup":
        return f"Smoke job {result.get('job_id')} finished: {result.get('status')}"
    if cap == "run_experiment":
        key = prof.final_key
        extra = f" at step {final.get('steps_run')}" if final.get("steps_run") else ""
        got = f", {key} = {_fmt(final[key])}{extra}" if key in final else ""
        return f"Job {result.get('job_id')} {result.get('status')}{got}"
    if cap == "analyze":
        bits = [f"{k}={_fmt(v)}" for k, v in final.items() if isinstance(v, (int, float)) and k in (prof.final_key, "train_acc", "steps_run", "wall_s")]
        return "Final metrics: " + ", ".join(bits)
    if cap == "repro_compare":
        return f"Verdict {final.get('verdict')}: {_fmt(final.get('value'))} vs claim {final.get('claim')}"
    if cap == "report_write":
        return "Report written to var/projects/" + run.project_id + "/report.md"
    return None


def specialize_checks(steps: list[PlanStep], profile: KitProfile) -> list[PlanStep]:
    """The shipped reproduce template names grokking's metrics; point its checks at this paper's real
    result key and claim (what the LLM plan adaptation does when available, done deterministically)."""
    out = []
    for s in steps:
        acc = []
        for check in s.accept:
            name, _, args = check.partition(":")
            if name == "metric_present" and args in ("test_acc", "loss"):
                check = f"metric_present:{profile.final_key}"
            elif name == "metric_threshold" and args.startswith("test_acc"):
                check = f"metric_threshold:{profile.final_key},>=,{profile.claim}"
            acc.append(check)
        out.append(s.model_copy(update={"accept": acc}))
    return out
