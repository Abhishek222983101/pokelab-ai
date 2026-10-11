/**
 * P9.8 — the binding audit. Not a Playwright click-through (that's the
 * manual verification already done for P9.1-9.7); this is a structural
 * check that the "nothing on screen exists without a real event behind
 * it" rule is actually enforced in the CODE, not just true by
 * convention. If someone adds a `useLabStore.setState({agents: {...}})`
 * call outside `applyEvent`, this test catches it.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const WEB_ROOT = join(__dirname, "..", "..");

function readAllTsFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".next" || entry.name === "out" || entry.name === "__tests__") continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      readAllTsFiles(full, out);
    } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

describe("binding audit — the store is the only path from event to screen", () => {
  // the store half of the audit lives in lib/__tests__/storeAudit.test.ts (reducer is the only path)

  it("no game scene calls useLabStore.setState directly (would bypass the event fold)", () => {
    const sceneFiles = readAllTsFiles(join(WEB_ROOT, "game"));
    for (const file of sceneFiles) {
      const source = readFileSync(file, "utf-8");
      expect(source, `${file} must not call setState directly`).not.toMatch(/useLabStore\.setState/);
    }
  });

  it("AgentEntity never invents its own agent id — it's always constructed with one from the store", () => {
    const source = readFileSync(join(WEB_ROOT, "game", "world", "AgentEntity.ts"), "utf-8");
    // the constructor takes agentId as a required parameter, not generated internally (e.g. no Math.random id)
    expect(source).toMatch(/constructor\([^)]*agentId: string/);
    expect(source).not.toMatch(/Math\.random/);
  });

  it("every scene that renders live state mounts the Shift+E binding overlay", () => {
    for (const name of ["RegionScene.ts", "LabScene.ts", "GymScene.ts"]) {
      const source = readFileSync(join(WEB_ROOT, "game", "scenes", name), "utf-8");
      expect(source, `${name} must mount the binding overlay`).toMatch(/mountBindingOverlay\(this\)/);
    }
  });
});
