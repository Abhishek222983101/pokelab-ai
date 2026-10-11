import { describe, expect, it } from "vitest";
import { Director } from "../director";
import type { AnimTask } from "../types";

function walk(entity: string, seq: number): AnimTask {
  return { entity, seq, kind: "walk", minMs: 300, maxMs: 600, skippable: true };
}

function bubble(entity: string, seq: number, text: string): AnimTask {
  return { entity, seq, kind: "bubble", minMs: 500, maxMs: 1500, skippable: true, data: { text } };
}

function battleTurn(entity: string, seq: number, deltaPct: number): AnimTask {
  return { entity, seq, kind: "battle_turn", minMs: 1000, maxMs: 1500, skippable: false, data: { deltaPct } };
}

describe("Director — per-entity FIFO, no cross-entity interference", () => {
  it("keeps separate queues for different entities", () => {
    let t = 0;
    const director = new Director(() => t);
    director.recordEventArrival("agent-a");
    director.enqueue(walk("agent-a", 1));
    director.recordEventArrival("agent-b");
    director.enqueue(walk("agent-b", 1));

    expect(director.queueFor("agent-a").length).toBe(1);
    expect(director.queueFor("agent-b").length).toBe(1);
  });
});

describe("Director — real-time-bound compression (§9.5 rule 2)", () => {
  it("does NOT compress while within the 1.5s lag budget", () => {
    let t = 0;
    const director = new Director(() => t);
    director.recordEventArrival("agent-a", 0);
    t = 500; // within budget
    director.enqueue(walk("agent-a", 1));
    director.enqueue(walk("agent-a", 2));

    expect(director.queueFor("agent-a").length).toBe(2);
  });

  it("collapses multiple queued walks into one fast teleport once lag exceeds 1.5s", () => {
    let t = 0;
    const director = new Director(() => t);
    director.recordEventArrival("agent-a", 0);
    t = 2000; // 2s lag — over the 1.5s threshold
    director.enqueue(walk("agent-a", 1));
    director.enqueue(walk("agent-a", 2));
    director.enqueue(walk("agent-a", 3));

    const queue = director.queueFor("agent-a");
    expect(queue.length).toBe(1);
    expect(queue[0].maxMs).toBeLessThanOrEqual(50); // teleport, not a 600ms walk
    expect(queue[0].seq).toBe(3); // kept the latest
  });

  it("keeps only the latest bubble text when lagging", () => {
    let t = 0;
    const director = new Director(() => t);
    director.recordEventArrival("agent-a", 0);
    t = 2000;
    director.enqueue(bubble("agent-a", 1, "thinking..."));
    director.enqueue(bubble("agent-a", 2, "running the kit..."));
    director.enqueue(bubble("agent-a", 3, "grokked!"));

    const queue = director.queueFor("agent-a");
    expect(queue.length).toBe(1);
    expect(queue[0].data?.text).toBe("grokked!");
  });

  it("summarizes batched battle turns into one delta instead of discarding them", () => {
    let t = 0;
    const director = new Director(() => t);
    director.recordEventArrival("agent-a", 0);
    t = 2000;
    director.enqueue(battleTurn("agent-a", 1, 12));
    director.enqueue(battleTurn("agent-a", 2, 8));
    director.enqueue(battleTurn("agent-a", 3, 15));

    const queue = director.queueFor("agent-a");
    expect(queue.length).toBe(1);
    expect(queue[0].data?.summary).toBe("3 checkpoints: +35.0%");
  });

  it("preserves relative seq order across different compressed kinds", () => {
    let t = 0;
    const director = new Director(() => t);
    director.recordEventArrival("agent-a", 0);
    t = 2000;
    director.enqueue(walk("agent-a", 1));
    director.enqueue(bubble("agent-a", 2, "hi"));
    director.enqueue(walk("agent-a", 3));
    director.enqueue(bubble("agent-a", 4, "bye"));

    const queue = director.queueFor("agent-a");
    const seqs = queue.map((t) => t.seq);
    expect(seqs).toEqual([...seqs].sort((a, b) => a - b));
  });
});

describe("Director — overlays (§9.5 rule 3)", () => {
  it("plays up to 2 queued overlays and toasts the rest", () => {
    const director = new Director();
    director.enqueue({ entity: "global", seq: 1, kind: "overlay", minMs: 4000, maxMs: 4000, skippable: true });
    director.enqueue({ entity: "global", seq: 2, kind: "overlay", minMs: 4000, maxMs: 4000, skippable: true });
    director.enqueue({ entity: "global", seq: 3, kind: "overlay", minMs: 4000, maxMs: 4000, skippable: true });

    const { toPlay, toasts } = director.drainOverlayQueue();
    expect(toPlay.length).toBe(2);
    expect(toasts.length).toBe(1);
    expect(toasts[0].seq).toBe(3);
  });
});
