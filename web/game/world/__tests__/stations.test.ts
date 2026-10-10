import { describe, expect, it } from "vitest";
import { allKnownCapabilities, stationFor } from "../stations";

describe("stationFor", () => {
  it("maps a real agent's capabilities to the right station", () => {
    expect(stationFor(["run_kit", "run_experiment"])).toBe("arena_door");
    expect(stationFor(["read_paper", "paper_read"])).toBe("library_desk");
  });

  it("picks the first capability that has a mapping, in declared order", () => {
    expect(stationFor(["run_kit", "debug", "implement"])).toBe("pokemon_center");
  });

  it("returns null when nothing maps", () => {
    expect(stationFor(["run_kit", "some_unmapped_cap"])).toBeNull();
  });

  it("every known capability resolves to a station", () => {
    for (const cap of allKnownCapabilities()) {
      expect(stationFor([cap])).not.toBeNull();
    }
  });
});
