/**
 * The Director (§9.5): per-entity FIFO animation queues, with the
 * real-time-bound compression rule — if an entity's queue has fallen
 * more than 1.5s behind the newest event for it, walking collapses to a
 * teleport, only the latest bubble survives, and battle turns are
 * batched into one summary. This is what keeps a flood of fast events
 * (a 15-second GPU job emitting 60 metric points) from queuing up 60
 * seconds of walk-and-narrate animation — the game can lag, but it can
 * never drift out of sync with what actually happened.
 */
import type { AnimKind, AnimTask, CompressedTask } from "./types";

const LAG_COMPRESSION_THRESHOLD_MS = 1500;
const MAX_QUEUED_OVERLAYS_BEFORE_TOAST = 2;

interface EntityQueue {
  entity: string;
  tasks: AnimTask[];
  lastEventAtMs: number;
}

export class Director {
  private queues = new Map<string, EntityQueue>();
  private overlayQueue: AnimTask[] = [];
  private now: () => number;

  constructor(nowFn: () => number = () => Date.now()) {
    this.now = nowFn;
  }

  /** Called once per incoming event, BEFORE enqueueing its task — this is
   * what lets `maybeCompress` know how far behind the queue has fallen. */
  recordEventArrival(entity: string, atMs?: number): void {
    const q = this.ensureQueue(entity);
    q.lastEventAtMs = atMs ?? this.now();
  }

  enqueue(task: AnimTask): void {
    if (task.kind === "overlay") {
      this.overlayQueue.push(task);
      return;
    }
    const q = this.ensureQueue(task.entity);
    q.tasks.push(task);
    this.maybeCompress(q);
  }

  /** §9.5 rule 2. Only ever shrinks a queue, never reorders it — the
   * surviving tasks are always a suffix of what was there (keeping the
   * most recent, most relevant state), never a reshuffle. */
  private maybeCompress(q: EntityQueue): void {
    const lagMs = this.now() - q.lastEventAtMs;
    if (lagMs <= LAG_COMPRESSION_THRESHOLD_MS || q.tasks.length < 2) return;

    const byKind = new Map<AnimKind, AnimTask[]>();
    for (const t of q.tasks) {
      const bucket = byKind.get(t.kind) ?? [];
      bucket.push(t);
      byKind.set(t.kind, bucket);
    }

    const compressed: AnimTask[] = [];
    for (const [kind, tasks] of byKind) {
      if (tasks.length === 1) {
        compressed.push(tasks[0]);
        continue;
      }
      compressed.push(this.compressGroup(kind, tasks));
    }
    // preserve original relative order of each kind's LAST occurrence,
    // so "walk then bubble then walk" still ends on the right visual beat
    compressed.sort((a, b) => a.seq - b.seq);
    q.tasks = compressed;
  }

  private compressGroup(kind: AnimKind, tasks: AnimTask[]): CompressedTask {
    const last = tasks[tasks.length - 1];
    if (kind === "walk") {
      return { ...last, minMs: 0, maxMs: 50, skippable: true, compressed: true, originalCount: tasks.length };
    }
    if (kind === "bubble") {
      // only the latest text survives — §9.5 rule 2
      return { ...last, compressed: true, originalCount: tasks.length };
    }
    if (kind === "battle_turn") {
      // Tasks being merged may themselves already be compressed (this
      // runs again on every enqueue while still lagging) — read each
      // one's own aggregate (totalDeltaPct/count) rather than its raw
      // deltaPct, or a re-compression silently drops everything folded
      // into an earlier pass. [BUG FOUND via a failing test: re-merging
      // used to recompute from `deltaPct` alone and lost prior history.]
      let totalDelta = 0;
      let count = 0;
      for (const t of tasks) {
        const alreadyAggregated = (t as CompressedTask).compressed;
        totalDelta += (t.data?.totalDeltaPct as number) ?? (t.data?.deltaPct as number) ?? 0;
        count += alreadyAggregated ? (t as CompressedTask).originalCount : 1;
      }
      return {
        ...last,
        data: { ...last.data, totalDeltaPct: totalDelta, summary: `${count} checkpoints: ${totalDelta >= 0 ? "+" : ""}${totalDelta.toFixed(1)}%` },
        compressed: true,
        originalCount: count,
      };
    }
    return { ...last, compressed: true, originalCount: tasks.length };
  }

  /** §9.5 rule 3: overlays beyond 2 queued become toasts instead of
   * playing serially forever. */
  drainOverlayQueue(): { toPlay: AnimTask[]; toasts: AnimTask[] } {
    const toPlay = this.overlayQueue.slice(0, MAX_QUEUED_OVERLAYS_BEFORE_TOAST);
    const toasts = this.overlayQueue.slice(MAX_QUEUED_OVERLAYS_BEFORE_TOAST);
    this.overlayQueue = [];
    return { toPlay, toasts };
  }

  queueFor(entity: string): AnimTask[] {
    return this.ensureQueue(entity).tasks;
  }

  popNext(entity: string): AnimTask | undefined {
    return this.ensureQueue(entity).tasks.shift();
  }

  private ensureQueue(entity: string): EntityQueue {
    let q = this.queues.get(entity);
    if (!q) {
      q = { entity, tasks: [], lastEventAtMs: this.now() };
      this.queues.set(entity, q);
    }
    return q;
  }
}
