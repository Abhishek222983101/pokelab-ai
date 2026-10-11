/**
 * The region/lab grid (P9.2/P9.3): real grid-engine (GridEngineHeadless)
 * logic — movement, collision, pathfinding — driven by a plain 0/1
 * ArrayTilemap instead of a Tiled JSON asset. We don't have licensed
 * overworld tile art beyond the Showdown battle sprites, so the grid
 * itself is procedural; the MOVEMENT ENGINE underneath is the real
 * grid-engine 2.45.0 pinned dependency, not a hand-rolled substitute.
 * Phaser rendering (RegionScene.ts) just reads positions out of this.
 */
import { ArrayTilemap, Direction, GridEngineHeadless } from "grid-engine";

export const TILE_SIZE = 32;
export const GRID_WIDTH = 20;
export const GRID_HEIGHT = 14;

export interface Building {
  id: string;
  label: string;
  x: number; // top-left tile
  y: number;
  w: number;
  h: number;
  color: string;
}

// A small town: Lab (center), Gym, Pokémon Center, Library — matches the
// cast from the architecture doc's concept map (§2.5).
export const BUILDINGS: Building[] = [
  { id: "lab", label: "Lab", x: 8, y: 4, w: 4, h: 3, color: "#3a5a8c" },
  { id: "gym", label: "Gym", x: 14, y: 4, w: 4, h: 3, color: "#8c3a3a" },
  { id: "pc", label: "Pokémon Center", x: 2, y: 4, w: 4, h: 3, color: "#3a8c5a" },
  { id: "library", label: "Library", x: 8, y: 9, w: 4, h: 3, color: "#8c7a3a" },
];

function buildCollisionGrid(): number[][] {
  const grid: number[][] = Array.from({ length: GRID_HEIGHT }, () => Array(GRID_WIDTH).fill(0));
  for (const b of BUILDINGS) {
    for (let y = b.y; y < b.y + b.h; y++) {
      for (let x = b.x; x < b.x + b.w; x++) {
        if (y < GRID_HEIGHT && x < GRID_WIDTH) grid[y][x] = 1; // blocked — walk around, not through
      }
    }
  }
  return grid;
}

export interface GridCharacterStart {
  id: string;
  x: number;
  y: number;
}

export function createGridWorld(characters: GridCharacterStart[]): GridEngineHeadless {
  const tilemap = new ArrayTilemap({
    ground: { data: buildCollisionGrid() },
  });
  const engine = new GridEngineHeadless();
  engine.create(tilemap, {
    characters: characters.map((c) => ({
      id: c.id,
      startPosition: { x: c.x, y: c.y },
      speed: 4,
    })),
  });
  return engine;
}

export { Direction };
