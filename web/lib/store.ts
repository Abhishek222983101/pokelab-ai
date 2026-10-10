/**
 * The console's event-fold state (mirrors brain's state.py — the same
 * discipline applies here: the ONLY way state changes is by folding an
 * event, never a direct setter from a button click).
 */
import { create } from "zustand";
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

interface LabStoreState {
  connectionStatus: "connecting" | "open" | "closed";
  lastSeq: number;
  jobs: Record<string, JobViewState>;
  recentEvents: LabEvent[]; // most-recent-first, capped
  setConnectionStatus: (s: "connecting" | "open" | "closed") => void;
  applyEvent: (e: LabEvent) => void;
}

const MAX_RECENT_EVENTS = 200;

export const useLabStore = create<LabStoreState>((set) => ({
  connectionStatus: "connecting",
  lastSeq: 0,
  jobs: {},
  recentEvents: [],

  setConnectionStatus: (s) => set({ connectionStatus: s }),

  applyEvent: (e) =>
    set((state) => {
      const next: LabStoreState = {
        ...state,
        lastSeq: Math.max(state.lastSeq, e.seq),
        recentEvents: [e, ...state.recentEvents].slice(0, MAX_RECENT_EVENTS),
      };

      if (e.kind === "job.metric") {
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
      }

      return next;
    }),
}));
