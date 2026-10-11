/**
 * Lab geometry (§9.4.2). Positions are a pure function of the station name — no randomness decides where
 * an agent stands. `slot` offsets spread several agents at one station side by side.
 */
import type { Station } from '@/lib/demo';

export const W = 960;
export const H = 640;
export const TILE = 48;
export const WALL_H = 144;

export interface StationDef { x: number; y: number; label: string; kind: 'shelf' | 'board' | 'table' | 'bench' | 'rack' | 'door' | 'desk' | 'rug' | 'gate' }

/** x,y = furniture centre-bottom; agents stand `STAND` px below. */
export const STATIONS: Record<Station, StationDef> = {
  library_desk: { x: 168, y: 232, label: 'LIBRARY', kind: 'shelf' },
  quest_board: { x: 480, y: 200, label: 'QUEST BOARD', kind: 'board' },
  analysis_table: { x: 752, y: 232, label: 'ANALYSIS', kind: 'table' },
  code_bench: { x: 168, y: 420, label: 'CODE BENCH', kind: 'bench' },
  server_rack: { x: 740, y: 420, label: 'SERVER RACK', kind: 'rack' },
  arena_door: { x: 900, y: 330, label: 'ARENA ▶', kind: 'gate' },
  scribe_desk: { x: 168, y: 556, label: 'SCRIBE', kind: 'desk' },
  lawn: { x: 760, y: 560, label: 'REST', kind: 'rug' },
  door: { x: 480, y: 632, label: 'FRONT DOOR', kind: 'door' },
};

export const STAND = 44;

export function standPoint(station: Station, slot: number): { x: number; y: number } {
  const s = STATIONS[station];
  if (station === 'door') return { x: s.x - 40 + slot * 56, y: s.y - 56 };
  if (station === 'lawn') return { x: s.x - 92 + (slot % 4) * 62, y: s.y - 20 + Math.floor(slot / 4) * 44 };
  if (station === 'arena_door') return { x: s.x - 36, y: s.y - 24 + slot * 46 };
  return { x: s.x - 46 + slot * 96, y: s.y + STAND };
}

export const OAK_HOME = { x: 480, y: 380 };
export const ASH_HOME = { x: 424, y: 392 };
