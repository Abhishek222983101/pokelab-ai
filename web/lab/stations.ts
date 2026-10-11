/**
 * Capability -> station mapping (§9.4.2) — deterministic, so every
 * agent's position in the Lab is derivable from its capabilities alone,
 * never assigned by hand.
 */

export type Station =
  | "library_desk" | "code_bench" | "server_rack" | "pokemon_center"
  | "quest_board" | "arena_door" | "analysis_table" | "scribe_desk";

const CAPABILITY_TO_STATION: Record<string, Station> = {
  paper_read: "library_desk", spec_extract: "library_desk", claim_extract: "library_desk",
  literature_search: "library_desk", paper_discover: "library_desk",
  implement: "code_bench", code_edit: "code_bench",
  env_setup: "server_rack", dependency_fix: "server_rack", data_prep: "server_rack",
  debug: "pokemon_center", repair: "pokemon_center",
  experiment_design: "quest_board", whatif_design: "quest_board",
  run_experiment: "arena_door", compute_ops: "arena_door", remote_run: "arena_door",
  analyze: "analysis_table", repro_compare: "analysis_table", explain: "analysis_table",
  report_write: "scribe_desk", notes: "scribe_desk", author_email: "scribe_desk",
};

/** An agent usually has several capabilities — the FIRST one (by the
 * agent's own declared order) that maps to a station wins, so spec
 * authors control priority just by listing capabilities in order. */
export function stationFor(capabilities: string[]): Station | null {
  for (const cap of capabilities) {
    const station = CAPABILITY_TO_STATION[cap];
    if (station) return station;
  }
  return null;
}

export function allKnownCapabilities(): string[] {
  return Object.keys(CAPABILITY_TO_STATION);
}
