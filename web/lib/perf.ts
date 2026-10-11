/**
 * P12.3 — performance instrumentation (AC-22: p95 event->screen < 150ms).
 * A tiny in-memory ring-buffer tracker, not a full APM — this project's
 * actual perf question is narrow (is the live demo fluid?), so the
 * answer only needs three real numbers: event->store latency, frame
 * time, and how often each panel actually re-renders.
 */
const MAX_SAMPLES = 500;

const eventLatenciesMs: number[] = [];
const frameTimesMs: number[] = [];
const panelRenderCounts: Record<string, number> = {};

function pushCapped(arr: number[], value: number): void {
  arr.push(value);
  if (arr.length > MAX_SAMPLES) arr.shift();
}

/** Called once per event the store actually applies — e.ts is the
 * server's real publish timestamp (set by lab-store at `hub.publish`
 * time), so this is genuine network+processing latency, not a
 * self-reported number the client could fake. */
export function recordEventLatency(serverTsIso: string): void {
  const sentMs = Date.parse(serverTsIso);
  if (Number.isNaN(sentMs)) return;
  const latency = Date.now() - sentMs;
  if (latency < 0 || latency > 60_000) return; // clock skew / stale fixture replay — not a real live sample
  pushCapped(eventLatenciesMs, latency);
}

export function recordFrameTime(deltaMs: number): void {
  pushCapped(frameTimesMs, deltaMs);
}

export function recordPanelRender(panel: string): void {
  panelRenderCounts[panel] = (panelRenderCounts[panel] ?? 0) + 1;
}

function percentile(sorted: number[], p: number): number | null {
  if (sorted.length === 0) return null;
  const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[idx];
}

export interface PerfSnapshot {
  eventLatencyMs: { n: number; p50: number | null; p95: number | null; p99: number | null };
  frameTimeMs: { n: number; p50: number | null; p95: number | null; avgFps: number | null };
  panelRenderCounts: Record<string, number>;
}

/** Clears all buffers — used by scripts/perf_probe.mjs right before it
 * starts generating real traffic, so the initial WS-handshake/backlog-
 * replay settle time doesn't pollute the "live" samples that follow. */
export function resetPerfBuffers(): void {
  eventLatenciesMs.length = 0;
  frameTimesMs.length = 0;
  for (const k of Object.keys(panelRenderCounts)) delete panelRenderCounts[k];
}

export function getPerfSnapshot(): PerfSnapshot {
  const latSorted = [...eventLatenciesMs].sort((a, b) => a - b);
  const frameSorted = [...frameTimesMs].sort((a, b) => a - b);
  const avgFrame = frameTimesMs.length ? frameTimesMs.reduce((a, b) => a + b, 0) / frameTimesMs.length : null;
  return {
    eventLatencyMs: {
      n: latSorted.length,
      p50: percentile(latSorted, 50),
      p95: percentile(latSorted, 95),
      p99: percentile(latSorted, 99),
    },
    frameTimeMs: {
      n: frameSorted.length,
      p50: percentile(frameSorted, 50),
      p95: percentile(frameSorted, 95),
      avgFps: avgFrame ? 1000 / avgFrame : null,
    },
    panelRenderCounts: { ...panelRenderCounts },
  };
}

// exposed so a real Playwright probe (scripts/perf_probe.mjs) can pull a
// live snapshot straight out of a running page — not a mock endpoint.
if (typeof window !== "undefined") {
  (window as unknown as { __pokelabPerf: () => PerfSnapshot }).__pokelabPerf = getPerfSnapshot;
  (window as unknown as { __pokelabPerfReset: () => void }).__pokelabPerfReset = resetPerfBuffers;
}
