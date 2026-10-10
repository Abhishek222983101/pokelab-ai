import { describe, expect, it, beforeEach } from "vitest";
import { useLabStore } from "../store";
import type { LabEvent } from "../labSocket";

function metricEvent(seq: number, jobId: string, step: number, k: string, v: number): LabEvent {
  return {
    seq, ts: "2026-01-01T00:00:00Z", kind: "job.metric", v: 1,
    project: "p1", actor: "labd", corr: null, causation: null,
    payload: { job_id: jobId, step, k, v },
  };
}

function doneEvent(seq: number, jobId: string, status: string, final: Record<string, unknown>): LabEvent {
  return {
    seq, ts: "2026-01-01T00:00:01Z", kind: "job.done", v: 1,
    project: "p1", actor: "labd", corr: null, causation: null,
    payload: { job_id: jobId, status, final, error_sig: null },
  };
}

beforeEach(() => {
  useLabStore.setState({ connectionStatus: "connecting", lastSeq: 0, jobs: {}, recentEvents: [] });
});

describe("useLabStore", () => {
  it("accumulates metrics for a job across events", () => {
    const { applyEvent } = useLabStore.getState();
    applyEvent(metricEvent(1, "job-1", 1, "loss", 0.9));
    applyEvent(metricEvent(2, "job-1", 2, "loss", 0.8));

    const job = useLabStore.getState().jobs["job-1"];
    expect(job.metrics.loss).toEqual([[1, 0.9], [2, 0.8]]);
    expect(job.status).toBe("running");
  });

  it("marks a job done and stores its final result", () => {
    const { applyEvent } = useLabStore.getState();
    applyEvent(metricEvent(1, "job-1", 1, "test_acc", 0.5));
    applyEvent(doneEvent(2, "job-1", "ok", { test_acc: 0.9654 }));

    const job = useLabStore.getState().jobs["job-1"];
    expect(job.status).toBe("ok");
    expect(job.final).toEqual({ test_acc: 0.9654 });
  });

  it("tracks lastSeq monotonically even with out-of-order-looking calls", () => {
    const { applyEvent } = useLabStore.getState();
    applyEvent(metricEvent(5, "job-1", 1, "loss", 0.9));
    applyEvent(metricEvent(3, "job-1", 2, "loss", 0.8)); // a lower seq, shouldn't regress lastSeq
    expect(useLabStore.getState().lastSeq).toBe(5);
  });

  it("caps recentEvents at 200 and keeps most-recent-first", () => {
    const { applyEvent } = useLabStore.getState();
    for (let i = 1; i <= 210; i++) {
      applyEvent(metricEvent(i, "job-1", i, "loss", 1 / i));
    }
    const recent = useLabStore.getState().recentEvents;
    expect(recent.length).toBe(200);
    expect(recent[0].seq).toBe(210);
  });
});
