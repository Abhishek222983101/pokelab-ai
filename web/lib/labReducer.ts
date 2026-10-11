/**
 * The lab's event fold (§9.2): a PURE function (state, event) -> state. It is the only way the
 * console, the phone and the game learn anything — no component sets lab state directly, and every
 * field below is derivable from the event log alone (replaying the log rebuilds the same view).
 */
import type { LabEvent } from "./labSocket";

export interface JobViewState {
  jobId: string;
  kit?: string;
  project?: string | null;
  status: "running" | "ok" | "error" | "stopped" | "timeout";
  metrics: Record<string, Array<[number, number | null]>>;
  final: Record<string, unknown> | null;
  errorSig: string | null;
}

export interface CurrentTask {
  stepId: string;
  capability: string;
  title: string;
  projectId: string | null;
  kit: string | null;
  seq: number;
}

export interface AgentViewState {
  agentId: string;
  species: string;
  role: string;
  version: number;
  status: "active" | "retired";
  capabilities: string[];
  reason: string;
  spawnedAtSeq: number;
  retiredAtSeq?: number;
  recommendations: Array<{ kind: "refine" | "merge"; reason: string; seq: number }>;
  /** Set by agent.task_started, cleared by task_finished/failed — the only thing that moves an agent. */
  currentTask: CurrentTask | null;
  lastOutcome: { ok: boolean; stepId: string; seq: number } | null;
  tasksDone: number;
  lastReward: number | null;
  posteriorMean: number | null;
}

export interface PlanStepView {
  stepId: string;
  capability: string;
  title: string;
  after: string[];
  status: "pending" | "running" | "done" | "failed";
  agentId: string | null;
}

export interface ProjectViewState {
  projectId: string;
  title: string;
  paper: string | null;
  kit: string | null;
  text: string;
  status: "running" | "completed";
  plan: PlanStepView[];
  claim: { metric: string; value: number } | null;
  verdict: string | null;
  value: number | null;
  jobId: string | null;
  badge: boolean;
  createdSeq: number;
}

export interface LabView {
  lastSeq: number;
  jobs: Record<string, JobViewState>;
  agents: Record<string, AgentViewState>;
  projects: Record<string, ProjectViewState>;
  /** Requests Oak declined, with its reason (shown, never silently dropped). */
  rejected: Array<{ seq: number; text: string; reason: string }>;
  recentEvents: LabEvent[]; // most-recent-first, capped
}

export const MAX_RECENT_EVENTS = 200;

export const emptyLabView = (): LabView => ({
  lastSeq: 0, jobs: {}, agents: {}, projects: {}, rejected: [], recentEvents: [],
});

const s = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);
const n = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

function job(view: LabView, e: LabEvent, jobId: string): JobViewState {
  return view.jobs[jobId] ?? { jobId, project: e.project, status: "running", metrics: {}, final: null, errorSig: null };
}

function patchAgent(view: LabView, agentId: string, fn: (a: AgentViewState) => AgentViewState): LabView {
  const a = view.agents[agentId];
  return a ? { ...view, agents: { ...view.agents, [agentId]: fn(a) } } : view;
}

function patchStep(view: LabView, projectId: unknown, stepId: string, fn: (st: PlanStepView) => PlanStepView): LabView {
  const p = typeof projectId === "string" ? view.projects[projectId] : undefined;
  if (!p) return view;
  return { ...view, projects: { ...view.projects, [p.projectId]: { ...p, plan: p.plan.map((st) => (st.stepId === stepId ? fn(st) : st)) } } };
}

export function reduce(prev: LabView, e: LabEvent): LabView {
  // §9.2: duplicates from a reconnect replay (seq <= last applied) change nothing
  if (prev.lastSeq > 0 && e.seq <= prev.lastSeq) return prev;
  let view: LabView = {
    ...prev,
    lastSeq: Math.max(prev.lastSeq, e.seq),
    recentEvents: [e, ...prev.recentEvents].slice(0, MAX_RECENT_EVENTS),
  };
  const p = e.payload;

  switch (e.kind) {
    case "job.started": {
      const id = s(p.job_id);
      view = { ...view, jobs: { ...view.jobs, [id]: { ...job(view, e, id), kit: s(p.kit) } } };
      break;
    }
    case "job.metric": {
      const id = s(p.job_id);
      const j = job(view, e, id);
      const key = s(p.k);
      const metrics = { ...j.metrics, [key]: [...(j.metrics[key] ?? []), [p.step as number, (p.v as number | null) ?? null] as [number, number | null]] };
      view = { ...view, jobs: { ...view.jobs, [id]: { ...j, metrics } } };
      break;
    }
    case "job.done": {
      const id = s(p.job_id);
      view = {
        ...view,
        jobs: {
          ...view.jobs,
          [id]: {
            ...job(view, e, id),
            status: p.status as JobViewState["status"],
            final: (p.final as Record<string, unknown>) ?? null,
            errorSig: (p.error_sig as string | null) ?? null,
          },
        },
      };
      break;
    }
    case "agent.spawned": {
      const id = s(p.agent_id);
      const caps = Array.isArray(p.capabilities) ? (p.capabilities as string[]) : [s(p.capability)].filter(Boolean);
      view = {
        ...view,
        agents: {
          ...view.agents,
          [id]: {
            agentId: id,
            species: s(p.species, "eevee"),
            role: s(p.role, "Specialist"),
            version: n(p.version) ?? 1,
            status: "active",
            capabilities: caps,
            reason: s(p.reason),
            spawnedAtSeq: e.seq,
            recommendations: [],
            currentTask: null,
            lastOutcome: null,
            tasksDone: 0,
            lastReward: null,
            posteriorMean: null,
          },
        },
      };
      break;
    }
    case "agent.retired":
      view = patchAgent(view, s(p.agent_id), (a) => ({ ...a, status: "retired", retiredAtSeq: e.seq, reason: s(p.reason, a.reason), currentTask: null }));
      break;
    case "agent.refine_recommended":
    case "agent.merge_recommended": {
      const id = s(p.agent_id) || (p.parents as string[] | undefined)?.[0] || "";
      const kind = e.kind === "agent.refine_recommended" ? "refine" : "merge";
      view = patchAgent(view, id, (a) => ({ ...a, recommendations: [...a.recommendations, { kind, reason: s(p.reason), seq: e.seq }] }));
      break;
    }
    case "agent.task_started": {
      const id = s(p.agent_id), stepId = s(p.step_id);
      view = patchAgent(view, id, (a) => ({
        ...a,
        currentTask: { stepId, capability: s(p.capability), title: s(p.title), projectId: (p.project_id as string) ?? null, kit: (p.kit as string) ?? null, seq: e.seq },
      }));
      view = patchStep(view, p.project_id, stepId, (st) => ({ ...st, status: "running", agentId: id }));
      break;
    }
    case "agent.task_finished":
    case "agent.task_failed": {
      const id = s(p.agent_id), stepId = s(p.step_id), ok = e.kind === "agent.task_finished";
      view = patchAgent(view, id, (a) => ({
        ...a,
        currentTask: a.currentTask?.stepId === stepId ? null : a.currentTask,
        lastOutcome: { ok, stepId, seq: e.seq },
        tasksDone: a.tasksDone + (ok ? 1 : 0),
      }));
      view = patchStep(view, p.project_id, stepId, (st) => ({ ...st, status: ok ? "done" : "failed" }));
      break;
    }
    case "agent.rewarded":
      view = patchAgent(view, s(p.agent_id), (a) => ({ ...a, lastReward: n(p.reward), posteriorMean: n(p.posterior_mean) ?? a.posteriorMean }));
      break;
    case "project.created": {
      const id = s(p.project_id);
      const plan = ((p.plan as Array<Record<string, unknown>>) ?? []).map((st) => ({
        stepId: s(st.step_id), capability: s(st.capability), title: s(st.title),
        after: (st.after as string[]) ?? [], status: "pending" as const, agentId: null,
      }));
      const claim = p.claim as { metric: string; value: number } | undefined;
      view = {
        ...view,
        projects: {
          ...view.projects,
          [id]: {
            projectId: id, title: s(p.title, id), paper: (p.paper as string) ?? null, kit: (p.kit as string) ?? null,
            text: s(p.text), status: "running", plan, claim: claim ?? null, verdict: null, value: null, jobId: null,
            badge: false, createdSeq: e.seq,
          },
        },
      };
      break;
    }
    case "project.completed": {
      const pr = view.projects[s(p.project_id)];
      if (pr) {
        view = {
          ...view,
          projects: { ...view.projects, [pr.projectId]: { ...pr, status: "completed", verdict: s(p.verdict) || null, value: n(p.value), jobId: (p.job_id as string) ?? null } },
        };
      }
      break;
    }
    case "project.badge_awarded": {
      const pr = view.projects[s(p.project_id)];
      if (pr) view = { ...view, projects: { ...view.projects, [pr.projectId]: { ...pr, badge: true } } };
      break;
    }
    case "project.rejected":
      view = { ...view, rejected: [...view.rejected, { seq: e.seq, text: s(p.text), reason: s(p.reason) }] };
      break;
  }
  return view;
}

/** Display level (§2.3: level = posterior mean reward x 100). */
export const levelOf = (a: AgentViewState) => Math.max(1, Math.round((a.posteriorMean ?? 0.5) * 100));
