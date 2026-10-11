/**
 * Hand-written to mirror contracts/pokelab_contracts/envelope.py exactly
 * (a full pydantic -> TS codegen pipeline is a real follow-on, tracked
 * in docs/PROGRESS.md P0.6 — this file is kept honest by the fixture
 * test below checking it against the SAME JSON files Python and Rust
 * validate, not by a generator that could silently drift).
 */
export interface LabEvent {
  seq: number;
  ts: string;
  kind: string;
  v: number;
  project: string | null;
  actor: string;
  corr: string | null;
  causation: number | null;
  payload: Record<string, unknown>;
  display?: Record<string, unknown> | null;
}
