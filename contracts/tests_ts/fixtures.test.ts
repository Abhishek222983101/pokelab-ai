import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { LabEvent } from "../ts/index";

const FIXTURES_DIR = join(__dirname, "..", "fixtures");

function load(name: string): LabEvent {
  return JSON.parse(readFileSync(join(FIXTURES_DIR, name), "utf-8"));
}

describe("contract fixtures parse as LabEvent (same files as Python/Rust)", () => {
  it("job_metric_event.json", () => {
    const e = load("job_metric_event.json");
    expect(e.kind).toBe("job.metric");
    expect(e.payload.job_id).toBe("job-1");
  });

  it("job_done_event.json", () => {
    const e = load("job_done_event.json");
    expect(e.kind).toBe("job.done");
    expect(e.payload.status).toBe("ok");
  });

  it("agent_spawned_event.json", () => {
    const e = load("agent_spawned_event.json");
    expect(e.kind).toBe("agent.spawned");
    expect(e.payload.capability).toBe("analyze_3d");
  });
});
