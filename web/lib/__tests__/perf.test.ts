import { describe, expect, it, vi } from "vitest";
import { getPerfSnapshot, recordEventLatency, recordFrameTime, recordPanelRender } from "../perf";

// perf.ts's buffers are module-level singletons (deliberately — a real
// running page has exactly one), so these tests measure DELTAS/relative
// behavior rather than assuming a pristine empty buffer, and never rely
// on running in isolation from each other.

describe("perf instrumentation (P12.3)", () => {
  it("computes real percentiles from recorded event latencies", () => {
    const now = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(now);
    const before = getPerfSnapshot().eventLatencyMs.n;
    for (const latencyMs of [10, 20, 30, 40, 1000]) {
      recordEventLatency(new Date(now - latencyMs).toISOString());
    }
    vi.restoreAllMocks();
    const after = getPerfSnapshot();
    expect(after.eventLatencyMs.n).toBe(before + 5);
    expect(after.eventLatencyMs.p95).toBe(1000); // the one clear outlier must land at/above p95
    expect(after.eventLatencyMs.p50!).toBeLessThan(after.eventLatencyMs.p95!);
  });

  it("ignores implausible latencies (clock skew / stale replay) rather than polluting the stats", () => {
    const before = getPerfSnapshot().eventLatencyMs.n;
    recordEventLatency(new Date(Date.now() + 5000).toISOString()); // "in the future" -> negative latency
    recordEventLatency(new Date(Date.now() - 10 * 60 * 1000).toISOString()); // 10 min old -> way past the 60s cutoff
    expect(getPerfSnapshot().eventLatencyMs.n).toBe(before); // neither was recorded
  });

  it("tracks frame time percentiles and derives fps from the real average", () => {
    for (let i = 0; i < 20; i++) recordFrameTime(16.67); // a steady 60fps, enough to dominate any prior samples
    const snap = getPerfSnapshot();
    expect(snap.frameTimeMs.n).toBeGreaterThan(0);
    expect(snap.frameTimeMs.avgFps).not.toBeNull();
    expect(snap.frameTimeMs.avgFps!).toBeGreaterThan(30); // loose — other tests may have pushed slower samples too
  });

  it("counts panel renders per named panel", () => {
    const before = getPerfSnapshot().panelRenderCounts["TestPanel"] ?? 0;
    recordPanelRender("TestPanel");
    recordPanelRender("TestPanel");
    expect(getPerfSnapshot().panelRenderCounts["TestPanel"]).toBe(before + 2);
  });
});
