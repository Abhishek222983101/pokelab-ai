/**
 * The console's event-fold state (mirrors brain's state.py — the same
 * discipline applies here: the ONLY way state changes is by folding an
 * event, never a direct setter from a button click).
 */
import { create } from "zustand";
import type { LabEvent } from "./labSocket";
import { recordEventLatency } from "./perf";

export interface JobViewState {
  jobId: string;
  kit?: string;
  project?: string | null;
  status: "running" | "ok" | "error" | "stopped" | "timeout";
  metrics: Record<string, Array<[number, number | null]>>;
  final: Record<string, unknown> | null;
  errorSig: string | null;
}

export interface AgentViewState {
  agentId: string;
  status: "active" | "retired";
  capabilities: string[];
  reason: string;
  spawnedAtSeq: number;
  retiredAtSeq?: number;
  recommendations: Array<{ kind: "refine" | "merge"; reason: string; seq: number }>;
}

interface LabStoreState {
  connectionStatus: "connecting" | "open" | "closed";
  lastSeq: number;
  jobs: Record<string, JobViewState>;
  agents: Record<string, AgentViewState>;
  recentEvents: LabEvent[]; // most-recent-first, capped
  setConnectionStatus: (s: "connecting" | "open" | "closed") => void;
  applyEvent: (e: LabEvent) => void;
}

const MAX_RECENT_EVENTS = 200;

export const useLabStore = create<LabStoreState>((set) => ({
  connectionStatus: "connecting",
  lastSeq: 0,
  jobs: {},
  agents: {},
  recentEvents: [],

  setConnectionStatus: (s) => set({ connectionStatus: s }),

  applyEvent: (e) => {
      recordEventLatency(e.ts);
      return set((state) => {
      const next: LabStoreState = {
        ...state,
        lastSeq: Math.max(state.lastSeq, e.seq),
        recentEvents: [e, ...state.recentEvents].slice(0, MAX_RECENT_EVENTS),
      };

      if (e.kind === "job.started") {
        const jobId = e.payload.job_id as string;
        const existing = next.jobs[jobId] ?? {
          jobId, project: e.project, status: "running", metrics: {}, final: null, errorSig: null,
        };
        next.jobs = { ...next.jobs, [jobId]: { ...existing, kit: e.payload.kit as string } };
      } else if (e.kind === "job.metric") {
        const jobId = e.payload.job_id as string;
        const key = e.payload.k as string;
        const step = e.payload.step as number;
        const value = e.payload.v as number | null;
        const existing = next.jobs[jobId] ?? {
          jobId, project: e.project, status: "running", metrics: {}, final: null, errorSig: null,
        };
        const metrics = { ...existing.metrics, [key]: [...(existing.metrics[key] ?? []), [step, value] as [number, number | null]] };
        next.jobs = { ...next.jobs, [jobId]: { ...existing, metrics } };
      } else if (e.kind === "job.done") {
        const jobId = e.payload.job_id as string;
        const existing = next.jobs[jobId] ?? {
          jobId, project: e.project, status: "running", metrics: {}, final: null, errorSig: null,
        };
        next.jobs = {
          ...next.jobs,
          [jobId]: {
            ...existing,
            status: e.payload.status as JobViewState["status"],
            final: (e.payload.final as Record<string, unknown>) ?? null,
            errorSig: (e.payload.error_sig as string | null) ?? null,
          },
        };
      } else if (e.kind === "agent.spawned") {
        const agentId = e.payload.agent_id as string;
        next.agents = {
          ...next.agents,
          [agentId]: {
            agentId,
            status: "active",
            capabilities: [e.payload.capability as string],
            reason: e.payload.reason as string,
            spawnedAtSeq: e.seq,
            recommendations: [],
          },
        };
      } else if (e.kind === "agent.retired") {
        const agentId = e.payload.agent_id as string;
        const existing = next.agents[agentId];
        if (existing) {
          next.agents = {
            ...next.agents,
            [agentId]: { ...existing, status: "retired", retiredAtSeq: e.seq, reason: e.payload.reason as string },
          };
        }
      } else if (e.kind === "agent.refine_recommended" || e.kind === "agent.merge_recommended") {
        const agentId = (e.payload.agent_id as string) ?? (e.payload.parents as string[])?.[0];
        const existing = next.agents[agentId];
        if (existing) {
          const kind = e.kind === "agent.refine_recommended" ? "refine" : "merge";
          next.agents = {
            ...next.agents,
            [agentId]: {
              ...existing,
              recommendations: [...existing.recommendations, { kind, reason: e.payload.reason as string, seq: e.seq }],
            },
          };
        }
      }

      return next;
    });
  },
}));
