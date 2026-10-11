/**
 * Where every agent is — a pure function of the store (SYSTEM-ARCHITECTURE §9.4.2, §2.5): its
 * current task's capability picks a station; idle agents sleep on the campus lawn; retired agents
 * are in Bill's PC (not on any map). No randomness and no client-side state decides a position, so
 * any two viewers of the same event log see the same world.
 */
import type { AgentViewState } from "@/lib/labReducer";
import { stationFor, type Station } from "./stations";
import { gymForKit } from "./gyms";

export type Pose = "sleep" | "idle" | "work";

export interface Placement {
  agentId: string;
  map: string;      // map registry key (game/overworld/campus.ts MAP, towns, interiors)
  anchor: string;   // anchor list name on that map
  slot: number;     // index among agents sharing (map, anchor), stable by agent id
  pose: Pose;
}

const LAB_STATIONS: ReadonlySet<Station> = new Set([
  "library_desk", "code_bench", "server_rack", "quest_board", "analysis_table", "scribe_desk", "arena_door",
]);

function spotFor(a: AgentViewState): { map: string; anchor: string; pose: Pose } {
  const task = a.currentTask;
  if (!task) return { map: "campus", anchor: "lawn", pose: "sleep" };
  if (task.capability === "run_experiment" || task.capability === "remote_run" || task.capability === "compute_ops") {
    const gym = gymForKit(task.kit ?? undefined);
    if (gym) return { map: `gym_${gym.town}`, anchor: "challenger", pose: "work" };
  }
  const station = stationFor([task.capability]);
  if (station === "pokemon_center") return { map: "center", anchor: "patients", pose: "work" };
  if (station && LAB_STATIONS.has(station)) return { map: "lab", anchor: station, pose: "work" };
  return { map: "lab", anchor: "quest_board", pose: "idle" };
}

export function placeAgents(agents: Record<string, AgentViewState>): Placement[] {
  const active = Object.values(agents).filter((a) => a.status === "active").sort((x, y) => x.agentId.localeCompare(y.agentId));
  const counts = new Map<string, number>();
  return active.map((a) => {
    const s = spotFor(a);
    const key = `${s.map}/${s.anchor}`;
    const slot = counts.get(key) ?? 0;
    counts.set(key, slot + 1);
    return { agentId: a.agentId, ...s, slot };
  });
}
