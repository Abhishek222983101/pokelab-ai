import { describe, expect, it } from "vitest";
import { placeAgents } from "../placement";
import type { AgentViewState, CurrentTask } from "@/lib/labReducer";

const agent = (id: string, task: Partial<CurrentTask> | null = null, status: "active" | "retired" = "active"): AgentViewState => ({
  agentId: id, species: id, role: "r", version: 1, status, capabilities: [], reason: "", spawnedAtSeq: 1, recommendations: [],
  currentTask: task ? { stepId: "s", capability: "", title: "", projectId: null, kit: null, seq: 2, ...task } : null,
  lastOutcome: null, tasksDone: 0, lastReward: null, posteriorMean: null, history: [], lineage: [],
});

describe("placeAgents (§9.4.2)", () => {
  it("idle agents sleep on the campus lawn, in stable slots", () => {
    const p = placeAgents({ zubat: agent("zubat"), abra: agent("abra") });
    expect(p).toEqual([
      { agentId: "abra", map: "campus", anchor: "lawn", slot: 0, pose: "sleep" },
      { agentId: "zubat", map: "campus", anchor: "lawn", slot: 1, pose: "sleep" },
    ]);
  });
  it("a task's capability picks the Lab station", () => {
    const [p] = placeAgents({ pikachu: agent("pikachu", { capability: "paper_read" }) });
    expect(p).toMatchObject({ map: "lab", anchor: "library_desk", pose: "work" });
    const [q] = placeAgents({ hoothoot: agent("hoothoot", { capability: "report_write" }) });
    expect(q).toMatchObject({ map: "lab", anchor: "scribe_desk" });
  });
  it("a run goes to that paper's Gym; debugging goes to the Pokémon Center", () => {
    const [p] = placeAgents({ porygon: agent("porygon", { capability: "run_experiment", kit: "grokking" }) });
    expect(p).toMatchObject({ map: "gym_modulo", anchor: "challenger" });
    const [q] = placeAgents({ squirtle: agent("squirtle", { capability: "debug" }) });
    expect(q).toMatchObject({ map: "center", anchor: "patients" });
  });
  it("retired agents are not on any map", () => {
    expect(placeAgents({ magnemite: agent("magnemite", null, "retired") })).toEqual([]);
  });
});
