/**
 * Binding audit, store half (§9.2): lab state changes ONLY by folding an event through the pure
 * reducer. Structural, not by convention — if someone adds a setter that writes agents/jobs/projects
 * from a click or a scene, or gives the reducer a side effect, this fails.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const LIB = join(__dirname, "..");
const store = readFileSync(join(LIB, "store.ts"), "utf-8");
const reducer = readFileSync(join(LIB, "labReducer.ts"), "utf-8");

describe("store audit — the reducer is the only path from event to state", () => {
  it("the only set() that touches lab state is set(state => reduce(state, e)) inside applyEvent", () => {
    const sets = store.match(/\bset\(([^;]*)\);/g) ?? [];
    const labSets = sets.filter((c) => !/^set\(\{\s*connectionStatus/.test(c));
    expect(labSets).toEqual(["set((state) => reduce(state, e));"]);
    expect(store.slice(store.indexOf("applyEvent:"))).toContain("reduce(state, e)");
    expect(store).not.toMatch(/\.(agents|jobs|projects)\s*=/);
  });

  it("the reducer is pure: no runtime imports, no clock, no randomness, no I/O", () => {
    const imports = reducer.match(/^import .*$/gm) ?? [];
    expect(imports.every((l) => l.startsWith("import type"))).toBe(true);
    expect(reducer).not.toMatch(/Math\.random|Date\.now|new Date|fetch\(|localStorage|setTimeout/);
  });
});
