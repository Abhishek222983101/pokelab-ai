import { describe, expect, it } from "vitest";
import { emptyLabView, reduce, levelOf, type LabView } from "../labReducer";
import type { LabEvent } from "../labSocket";

let seq = 0;
const ev = (kind: string, payload: Record<string, unknown>, project: string | null = null): LabEvent => ({
  seq: ++seq, ts: new Date().toISOString(), kind, v: 1, project, actor: "oak", corr: null, causation: null, payload, display: null,
});
const fold = (events: LabEvent[], from: LabView = emptyLabView()) => events.reduce(reduce, from);

describe("labReducer", () => {
  it("folds the base team with species, role, version and all capabilities", () => {
    const v = fold([ev("agent.spawned", { agent_id: "pikachu", species: "pikachu", role: "Paper Reader", version: 2, capabilities: ["paper_read", "spec_extract"], capability: "paper_read" })]);
    const a = v.agents.pikachu;
    expect([a.species, a.role, a.version]).toEqual(["pikachu", "Paper Reader", 2]);
    expect(a.capabilities).toEqual(["paper_read", "spec_extract"]);
    expect(a.currentTask).toBeNull();
  });

  it("a task start is the only thing that gives an agent a current task; finishing clears it", () => {
    const base = fold([
      ev("agent.spawned", { agent_id: "porygon", species: "porygon", capabilities: ["run_experiment"] }),
      ev("project.created", { project_id: "p1", title: "Reproduce grokking", paper: "grokking", kit: "grokking",
        plan: [{ step_id: "s6", capability: "run_experiment", title: "Full run", after: [] }] }),
    ]);
    const running = fold([ev("agent.task_started", { agent_id: "porygon", step_id: "s6", capability: "run_experiment", title: "Full run", project_id: "p1", kit: "grokking" })], base);
    expect(running.agents.porygon.currentTask).toMatchObject({ stepId: "s6", capability: "run_experiment", kit: "grokking", projectId: "p1" });
    expect(running.projects.p1.plan[0]).toMatchObject({ status: "running", agentId: "porygon" });

    const done = fold([
      ev("agent.task_finished", { agent_id: "porygon", step_id: "s6", project_id: "p1" }),
      ev("agent.rewarded", { agent_id: "porygon", step_id: "s6", reward: 0.91, posterior_mean: 0.74 }),
    ], running);
    expect(done.agents.porygon.currentTask).toBeNull();
    expect(done.agents.porygon.tasksDone).toBe(1);
    expect(done.projects.p1.plan[0].status).toBe("done");
    expect(levelOf(done.agents.porygon)).toBe(74);
  });

  it("a stale finish for an older step never clears a newer task", () => {
    const v = fold([
      ev("agent.spawned", { agent_id: "abra", capabilities: ["analyze", "repro_compare"] }),
      ev("agent.task_started", { agent_id: "abra", step_id: "s8", capability: "repro_compare", title: "Compare" }),
      ev("agent.task_failed", { agent_id: "abra", step_id: "s7" }),
    ]);
    expect(v.agents.abra.currentTask?.stepId).toBe("s8");
    expect(v.agents.abra.lastOutcome).toMatchObject({ ok: false, stepId: "s7" });
  });

  it("records the verdict and badge exactly as Oak published them", () => {
    const v = fold([
      ev("project.created", { project_id: "p2", title: "Reproduce materials", paper: "materials", plan: [] }),
      ev("project.completed", { project_id: "p2", verdict: "REPRODUCED", value: 0.913, job_id: "job-7" }),
      ev("project.badge_awarded", { project_id: "p2" }),
    ]);
    expect(v.projects.p2).toMatchObject({ status: "completed", verdict: "REPRODUCED", value: 0.913, jobId: "job-7", badge: true });
  });

  it("keeps rejected requests with Oak's reason instead of dropping them", () => {
    const v = fold([ev("project.rejected", { request_seq: 4, text: "teach me chess", reason: "no paper pack matches" })]);
    expect(v.rejected[0]).toMatchObject({ text: "teach me chess", reason: "no paper pack matches" });
  });

  it("ignores a replayed duplicate (seq <= last applied)", () => {
    const first = ev("agent.spawned", { agent_id: "zubat", capabilities: ["paper_discover"] });
    const v = fold([first, ev("agent.retired", { agent_id: "zubat", reason: "posterior low" })]);
    const again = reduce(v, first);
    expect(again).toBe(v);
    expect(again.agents.zubat.status).toBe("retired");
  });

  it("agent.evolved swaps the species and bumps the version, nothing else", () => {
    const v = fold([
      ev("agent.spawned", { agent_id: "charmander", species: "charmander", role: "Implementer", version: 1, capabilities: ["implement"] }),
      ev("agent.evolved", { agent_id: "charmander", from_species: "charmander", species: "charmeleon", version: 2, evidence: { n: 8, mean_reward: 0.95 } }),
    ]);
    expect([v.agents.charmander.species, v.agents.charmander.version, v.agents.charmander.role]).toEqual(["charmeleon", 2, "Implementer"]);
  });

  it("builds each agent's work log (context) from task, thought, finish and reward events", () => {
    const v = fold([
      ev("agent.spawned", { agent_id: "pikachu", species: "pikachu", role: "Paper Reader", version: 2, capabilities: ["paper_read"] }),
      ev("agent.task_started", { agent_id: "pikachu", step_id: "s1", capability: "paper_read", title: "Ingest the paper", project_id: "pX" }),
      ev("agent.thought", { agent_id: "pikachu", step_id: "s1", project_id: "pX", text: "Read 40 chunks" }),
      ev("agent.task_finished", { agent_id: "pikachu", step_id: "s1", project_id: "pX", job_id: null }),
      ev("agent.rewarded", { agent_id: "pikachu", step_id: "s1", project_id: "pX", reward: 0.97, posterior_mean: 0.9 }),
    ]);
    expect(v.agents.pikachu.history).toHaveLength(1);
    expect(v.agents.pikachu.history[0]).toMatchObject({ stepId: "s1", status: "done", reward: 0.97, thoughts: ["Read 40 chunks"] });
  });

  it("keeps the paper evidence per project and records de-evolution in the lineage", () => {
    const v = fold([
      ev("agent.spawned", { agent_id: "pikachu", species: "pikachu", role: "Paper Reader", version: 2, capabilities: [] }),
      ev("agent.evolved", { agent_id: "pikachu", from_species: "pikachu", species: "raichu", version: 3, evidence: { n: 8, mean_reward: 0.95 }, rule: "r" }),
      ev("agent.devolved", { agent_id: "pikachu", from_species: "raichu", species: "pikachu", version: 2, reason: "demo reset" }),
      ev("paper.ingested", { project_id: "pX", title: "Grokking", source: "pdf:x.pdf", n_chunks: 2, chunks: [{ id: "c1", text: "weight decay" }] }),
      ev("claim.extracted", { project_id: "pX", title: "Grokking", target: { metric: "test_acc", value: 0.95 }, claims: [{ metric: "test_acc", value: 0.95 }] }),
      ev("analysis.computed", { project_id: "pX", job_id: "job-1", metric: "test_acc", claim: 0.95, points: 23, claim_hit_step: 1900, train_saturated_step: 400, delay_steps: 1500 }),
    ]);
    expect([v.agents.pikachu.species, v.agents.pikachu.version]).toEqual(["pikachu", 2]);
    expect(v.agents.pikachu.lineage.map((l) => l.kind)).toEqual(["devolved", "evolved"]);
    expect(v.papers.pX.chunks[0].text).toBe("weight decay");
    expect(v.papers.pX.analysis).toMatchObject({ delaySteps: 1500, claimHitStep: 1900 });
  });

  it("fills the what-if map tile by tile from explore events", () => {
    const v = fold([
      ev("explore.planned", { project_id: "pW", title: "T", claim: 0.95, axes: { wd: [0, 1], frac: [0.5] }, cells: [] }),
      ev("explore.cell", { project_id: "pW", wd: 1, frac: 0.5, job_id: "job-1", status: "ok", test_acc: 0.99, train_acc: 1, claim_hit_step: 1900, train_saturated_step: 100 }),
      ev("explore.cell", { project_id: "pW", wd: 0, frac: 0.5, job_id: "job-2", status: "ok", test_acc: 0.4, train_acc: 1, claim_hit_step: null, train_saturated_step: 100 }),
      ev("explore.analysis", { project_id: "pW", lines: ["1 of 2 settings reached the claim."] }),
    ]);
    expect(v.explore.pW.cells).toHaveLength(2);
    expect(v.explore.pW.cells.find((c) => c.wd === 0)?.claimHitStep).toBeNull();
    expect(v.explore.pW.lines[0]).toMatch(/1 of 2/);
  });
});
