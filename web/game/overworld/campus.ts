/**
 * Pallet Campus (the hub town) and Oak's Lab interior — GAME-DESIGN.md §2/§3, SYSTEM-ARCHITECTURE
 * §2.5. Built with the PokeStonks `Builder` so every tile, autotile, tree wall and flood-fill rule is
 * the engine's own. Deterministic: the same build always yields the same map (no randomness decides
 * where anything is — pillar P1).
 *
 * Each builder also returns **anchors**: named lists of standing tiles. An agent's tile is a pure
 * function of (its current task's station, its index among agents at that station) — see
 * lab/placement.ts.
 */
import { hash2, hashStr, rng } from '../art/pixel';
import { TILE, gid, blobTile } from '../art/tileset';
import type { RouteTheme } from '../art/themes';
import { BLOCK, Builder, FREE, KEEP, PATH, floodFrom, neighbourMask, toTiled } from './maps';
import type { BuiltMap, Dir, MapMeta, NpcSpec, SignSpec, SpawnSpec, WarpSpec } from './mapTypes';
import { gymForTown } from '@/lab/gyms';

export interface Anchor { x: number; y: number; facing: Dir }
export type Anchors = Record<string, Anchor[]>;
export interface LabWorldMap extends BuiltMap { anchors: Anchors }

/** Map keys the scene registry uses (warp `to` values). */
export const MAP = {
  campus: 'campus',
  lab: 'lab',
  center: 'center',
  library: 'library',
  daycare: 'daycare',
  pcbox: 'pcbox',
  crystal: 'crystal',
  lumen: 'lumen',
  grove: 'grove',
  modulo: 'modulo',
  edgeport: 'edgeport',
} as const;
export type MapKey = (typeof MAP)[keyof typeof MAP];


/** Campus building footprints — the single source for door tiles on both sides of every warp. */
export const CAMPUS_BUILDINGS = {
  lab: { x: 20, y: 4, w: 7, style: 'LAB' as Style, roofRows: 2, wallRows: 2, doorCol: 3 },
  center: { x: 8, y: 9, w: 5, style: 'CTR' as Style, roofRows: 2, wallRows: 2, doorCol: 2 },
  library: { x: 35, y: 9, w: 5, style: 'LIB' as Style, roofRows: 2, wallRows: 2, doorCol: 2 },
  daycare: { x: 9, y: 21, w: 4, style: 'HOUSE' as Style, roofRows: 2, wallRows: 2, doorCol: 1 },
  pcbox: { x: 35, y: 21, w: 4, style: 'HOUSE' as Style, roofRows: 2, wallRows: 2, doorCol: 1 },
};
export type CampusBuilding = keyof typeof CAMPUS_BUILDINGS;
export function campusDoor(k: CampusBuilding): { x: number; y: number } {
  const c = CAMPUS_BUILDINGS[k];
  return { x: c.x + c.doorCol, y: c.y + c.roofRows + c.wallRows - 1 };
}
/** Where the player stands on the campus after walking out of a building. */
export const outsideDoor = (k: CampusBuilding): SpawnSpec => { const d = campusDoor(k); return { x: d.x, y: d.y + 1, facing: 'down' }; };

/** Spawn just inside a town's gate, for the edge the gate is on. */
export function townEntrySpawn(entry: 'n' | 's' | 'e' | 'w', w = TOWN_W, h = TOWN_H): SpawnSpec {
  switch (entry) {
    case 'n': return { x: TOWN_NORTH_ROAD_X, y: 2, facing: 'down' };
    case 's': return { x: Math.floor(w / 2) - 1, y: h - 3, facing: 'up' };
    case 'w': return { x: 2, y: TOWN_ROAD_Y, facing: 'right' };
    case 'e': return { x: w - 3, y: TOWN_ROAD_Y, facing: 'left' };
  }
}
export const TOWN_W = 40;
export const TOWN_H = 30;
export const TOWN_ROAD_Y = 15;
export const TOWN_NORTH_ROAD_X = 29;

export const CAMPUS_W = 48;
export const CAMPUS_H = 36;

export type Style = 'LAB' | 'CTR' | 'LIB' | 'GYM' | 'HOUSE';

const roofTiles = (s: Style, part: 'L' | 'M' | 'R', row: 'ridge' | 'eave'): number => {
  if (s === 'HOUSE') {
    if (row === 'ridge') return part === 'L' ? TILE.ROOF_TL : part === 'R' ? TILE.ROOF_TR : TILE.ROOF_TM;
    return part === 'L' ? TILE.ROOF_BL : part === 'R' ? TILE.ROOF_BR : TILE.ROOF_BM;
  }
  const k = `${s}_ROOF_${row === 'ridge' ? 'T' : 'B'}${part}` as keyof typeof TILE;
  return TILE[k];
};
const wallTile = (s: Style, kind: 'wall' | 'win' | 'door'): number => {
  if (s === 'HOUSE') return kind === 'wall' ? TILE.WALL : kind === 'win' ? TILE.WALL_WIN : TILE.DOOR;
  return TILE[`${s}_${kind === 'wall' ? 'WALL' : kind === 'win' ? 'WIN' : 'DOOR'}` as keyof typeof TILE];
};

/**
 * Places a building: `roofRows` rows of roof (first = ridge, rest = eave), then wall rows. The last
 * wall row holds the door at `doorCol`; `plate` (if any) sits on the first wall row, centred.
 * Returns the door tile (walkable, the warp lives there).
 */
export function building(
  b: Builder, x0: number, y0: number, w: number, style: Style,
  opts: { roofRows?: number; wallRows?: number; doorCol?: number; plate?: number },
): { doorX: number; doorY: number } {
  const roofRows = opts.roofRows ?? 2, wallRows = opts.wallRows ?? 2;
  const doorCol = opts.doorCol ?? Math.floor(w / 2);
  for (let r = 0; r < roofRows; r++) {
    for (let k = 0; k < w; k++) {
      const part = k === 0 ? 'L' : k === w - 1 ? 'R' : 'M';
      const x = x0 + k, y = y0 + r;
      b.setOver(x, y, roofTiles(style, part, r === 0 ? 'ridge' : 'eave'));
      b.collide[b.i(x, y)] = 1; b.occ[b.i(x, y)] = BLOCK;
    }
  }
  for (let r = 0; r < wallRows; r++) {
    const y = y0 + roofRows + r;
    const last = r === wallRows - 1;
    for (let k = 0; k < w; k++) {
      const x = x0 + k;
      let t = (k % 2 === (w % 2 === 0 ? 0 : 1)) ? wallTile(style, 'win') : wallTile(style, 'wall');
      if (r === 0 && opts.plate !== undefined && k === Math.floor(w / 2)) t = opts.plate;
      if (last && k === doorCol) t = wallTile(style, 'door');
      const isDoor = last && k === doorCol;
      b.setDecor(x, y, t, !isDoor);
      if (isDoor) b.occ[b.i(x, y)] = PATH;
    }
  }
  return { doorX: x0 + doorCol, doorY: y0 + roofRows + wallRows - 1 };
}

export function finishTerrain(b: Builder, spawn: SpawnSpec) {
  const { w, h } = b;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const idx = b.i(x, y);
    if (b.path[idx]) b.paths[idx] = gid(blobTile('path', neighbourMask(b.path, w, h, x, y, 1)));
    if (b.water[idx]) {
      const m = neighbourMask(b.water, w, h, x, y, 1);
      b.anim0[idx] = gid(blobTile('water0', m));
      b.anim1[idx] = gid(blobTile('water1', m));
    }
    if (b.tall[idx] && !b.collide[idx] && !b.path[idx]) {
      const v = hash2(x, y, 44) < 0.5;
      b.anim0[idx] = gid(v ? TILE.TALL_A0 : TILE.TALL_B0);
      b.anim1[idx] = gid(v ? TILE.TALL_A1 : TILE.TALL_B1);
    } else if (b.tall[idx]) b.tall[idx] = 0;
  }
  // any walkable pocket the player can never reach becomes a bush (same rule as PokeStonks)
  const reach = floodFrom(b.collide, w, h, spawn.x, spawn.y);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const idx = b.i(x, y);
    if (!b.collide[idx] && !reach[idx]) {
      b.decor[idx] = gid(TILE.BUSH); b.collide[idx] = 1; b.tall[idx] = 0; b.anim0[idx] = 0; b.anim1[idx] = 0;
    }
  }
}

/* ------------------------------------------------------------------ Pallet Campus ---- */

/** Gate in the tree wall → the town it leads to. */
export const CAMPUS_GATES: Array<{ to: MapKey; tiles: Array<[number, number]>; label: string; arrive: SpawnSpec }> = [
  { to: MAP.grove, tiles: [[31, 0], [32, 0]], label: 'ARENA GROVE (N)', arrive: { x: 31, y: 2, facing: 'down' } },
  { to: MAP.crystal, tiles: [[0, 15], [0, 16]], label: 'CRYSTAL CAVE (W)', arrive: { x: 2, y: 15, facing: 'right' } },
  { to: MAP.lumen, tiles: [[47, 15], [47, 16]], label: 'LUMEN TOWN (E)', arrive: { x: 45, y: 15, facing: 'left' } },
  { to: MAP.modulo, tiles: [[6, 35], [7, 35]], label: 'MODULO CITY (SW)', arrive: { x: 6, y: 33, facing: 'up' } },
  { to: MAP.edgeport, tiles: [[40, 35], [41, 35]], label: 'EDGE PORT (SE)', arrive: { x: 40, y: 33, facing: 'up' } },
];

export function buildCampus(theme: RouteTheme = 'bluechip'): LabWorldMap {
  const w = CAMPUS_W, h = CAMPUS_H;
  const b = new Builder(w, h);
  const rand = rng(hashStr(`pallet-campus:${theme}`));

  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const n = hash2(x, y, 5);
    b.ground[b.i(x, y)] = gid(n < 0.66 ? TILE.GRASS_A : n < 0.9 ? TILE.GRASS_B : TILE.GRASS_C);
  }

  const road = (x0: number, y0: number, x1: number, y1: number) => {
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (b.inb(x, y)) { b.path[b.i(x, y)] = 1; b.occ[b.i(x, y)] = PATH; }
  };
  const keep = (x0: number, y0: number, x1: number, y1: number) => {
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (b.inb(x, y) && b.occ[b.i(x, y)] === FREE) b.occ[b.i(x, y)] = KEEP;
  };

  // --- roads
  road(0, 15, w - 1, 16);          // east-west main street, gates W and E
  road(31, 0, 32, 14);             // north road to Arena Grove
  road(19, 8, 27, 10);             // plaza in front of Oak's Lab
  road(23, 11, 24, 14);            // plaza → main street
  road(23, 17, 24, 19);            // main street → campus lawn
  road(10, 13, 11, 14);            // Pokémon Center walkway
  road(37, 13, 38, 14);            // Library walkway
  road(6, 17, 7, h - 1);           // south-west road to Modulo City
  road(40, 17, 41, h - 1);         // south-east road to Edge Port
  road(8, 25, 13, 26);             // Day Care drive
  road(34, 25, 39, 26);            // Bill's PC drive

  // --- pond + Kaggle ferry dock (north-east)
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const u = (x + 0.5 - 41.2) / 3.6, v = (y + 0.5 - 5.2) / 2.4;
    if (u * u + v * v <= 1 + (hash2(x, y, 31) - 0.5) * 0.2 && !b.path[b.i(x, y)]) {
      const idx = b.i(x, y); b.water[idx] = 1; b.occ[idx] = BLOCK; b.collide[idx] = 1;
    }
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const idx = b.i(x, y);
    if (b.water[idx] || b.path[idx]) continue;
    let near = false;
    for (let j = -1; j <= 1 && !near; j++) for (let k = -1; k <= 1; k++) if (b.inb(x + k, y + j) && b.water[b.i(x + k, y + j)]) { near = true; break; }
    if (near) b.ground[idx] = gid(hash2(x, y, 8) < 0.5 ? TILE.SAND : TILE.SAND_B);
  }
  road(36, 6, 37, 14);             // path down to the dock

  // --- buildings
  const B = CAMPUS_BUILDINGS;
  const put = (k: CampusBuilding, plate: number) => building(b, B[k].x, B[k].y, B[k].w, B[k].style, { roofRows: B[k].roofRows, wallRows: B[k].wallRows, doorCol: B[k].doorCol, plate });
  const lab = put('lab', TILE.PLATE_FLASK);
  keep(19, 3, 27, 8);
  const center = put('center', TILE.PLATE_BALL);
  keep(7, 8, 13, 13);
  const library = put('library', TILE.PLATE_BOOK);
  keep(34, 8, 40, 13);
  const daycare = put('daycare', TILE.PLATE_EGG);
  keep(8, 20, 14, 25);
  const pcbox = put('pcbox', TILE.PLATE_MONITOR);
  keep(34, 20, 40, 25);
  road(daycare.doorX, daycare.doorY + 1, daycare.doorX, 25);
  road(pcbox.doorX, pcbox.doorY + 1, pcbox.doorX, 25);

  // --- Day Care yard fence (west of the house, open to the drive)
  for (let x = 2; x <= 7; x++) if (b.occ[b.i(x, 20)] === FREE) b.setDecor(x, 20, x === 2 ? TILE.FENCE_L : TILE.FENCE_H);
  for (let y = 21; y <= 23; y++) if (b.occ[b.i(2, y)] === FREE) b.setDecor(2, y, TILE.FENCE_V);
  keep(3, 21, 5, 23);

  // --- campus lawn: open grass ringed by flowers (idle agents sleep here)
  const LAWN = { x0: 17, y0: 20, x1: 30, y1: 29 };
  for (let y = LAWN.y0; y <= LAWN.y1; y++) for (let x = LAWN.x0; x <= LAWN.x1; x++) {
    const idx = b.i(x, y);
    if (b.occ[idx] !== FREE) continue;
    const ring = x === LAWN.x0 || x === LAWN.x1 || y === LAWN.y1;
    if (ring) b.ground[idx] = gid(TILE.FLOWER_A + ((x + y) % 3));
    else b.ground[idx] = gid(hash2(x, y, 9) < 0.8 ? TILE.GRASS_A : TILE.GRASS_B);
    b.occ[idx] = KEEP;
  }

  // --- lamps along the plaza and main street
  const tryTall = (x: number, y: number, top: number, bottom: number) => {
    if (!b.inb(x, y - 1) || b.occ[b.i(x, y)] === PATH || b.occ[b.i(x, y - 1)] === PATH) return false;
    b.setOver(x, y - 1, top); b.collide[b.i(x, y - 1)] = 1; b.occ[b.i(x, y - 1)] = BLOCK; b.setDecor(x, y, bottom);
    return true;
  };
  for (const [x, y] of [[18, 10], [28, 10], [15, 14], [21, 14], [27, 14], [34, 18], [15, 18], [22, 19], [25, 19]] as const) {
    b.occ[b.i(x, y)] = FREE; if (b.inb(x, y - 1) && b.occ[b.i(x, y - 1)] === KEEP) b.occ[b.i(x, y - 1)] = FREE;
    tryTall(x, y, TILE.LAMP_T, TILE.LAMP_B);
  }

  // --- signs (all real information or clearly-labelled directions)
  const signs: SignSpec[] = [];
  const addSign = (id: string, x: number, y: number, text: string[]) => {
    b.occ[b.i(x, y)] = FREE; b.setDecor(x, y, TILE.SIGN); signs.push({ id, x, y, text });
  };
  addSign('sign_campus', 26, 12, ['PALLET CAMPUS', 'Every battle here is a real training run.']);
  addSign('sign_lab', 19, 11, ["PROF. OAK'S LAB", 'Research HQ. Agents work at the stations inside.']);
  addSign('sign_center', 12, 14, ['POKéMON CENTER', 'Nurse Joy (the Medic) triages failed runs.']);
  addSign('sign_library', 36, 14, ['POKéDEX LIBRARY', 'The lab memory: past runs, lessons and fixes.']);
  addSign('sign_daycare', 14, 26, ['DAY CARE', 'Two agents enter, an egg hatches: a merged agent.']);
  addSign('sign_pc', 33, 26, ["BILL'S PC", 'Retired agents are stored here, with the reason.']);
  addSign('sign_lawn', 22, 18, ['CAMPUS LAWN', 'Agents with no task sleep here. Nothing is faked.']);
  addSign('sign_dock', 35, 8, ['KAGGLE ISLAND FERRY', 'Remote GPU jobs sail from this dock.']);
  addSign('sign_gate_n', 30, 2, ['NORTH: ARENA GROVE', "Erika's Gym — tabular comparison arena."]);
  addSign('sign_gate_w', 2, 13, ['WEST: CRYSTAL CAVE', "Brock's Gym — materials (Matbench)."]);
  addSign('sign_gate_e', 45, 13, ['EAST: LUMEN TOWN', "Blaine's Gym — 3D / Tiny NeRF."]);
  addSign('sign_gate_sw', 8, 32, ['SOUTH-WEST: MODULO CITY', "Sabrina's Gym — Grokking (CPU-scale ML)."]);
  addSign('sign_gate_se', 39, 32, ['SOUTH-EAST: EDGE PORT', "Lt. Surge's Gym — distillation (edge ML)."]);

  // --- border trees (2x2) leaving the five gates open
  const gateCells = new Set<number>();
  for (const g of CAMPUS_GATES) for (const [x, y] of g.tiles) {
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if (b.inb(x + dx, y + dy)) gateCells.add(b.i(x + dx, y + dy));
  }
  const plant = (x: number, y: number, v: number) => {
    for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) if (gateCells.has(b.i(x + dx, y + dy)) || b.path[b.i(x + dx, y + dy)]) return;
    b.plantTree(x, y, v);
  };
  for (let x = 0; x < w; x += 2) { plant(x, 0, (x >> 1) & 1); plant(x, h - 2, ((x >> 1) + 1) & 1); }
  for (let y = 2; y < h - 2; y += 2) { plant(0, y, (y >> 1) & 1); plant(w - 2, y, ((y >> 1) + 1) & 1); }

  const scatter = (count: number, fn: (x: number, y: number) => boolean, tries = 400, margin = 3) => {
    let placed = 0;
    for (let t = 0; t < tries && placed < count; t++) {
      const x = margin + Math.floor(rand() * (w - margin * 2)), y = margin + Math.floor(rand() * (h - margin * 2));
      if (fn(x, y)) placed++;
    }
  };
  // groves: denser near the border so the campus feels enclosed, a few inside
  scatter(70, (x, y) => {
    const edge = Math.min(x, y, w - 1 - x, h - 1 - y);
    if (edge > 6 || !b.areaFree(x, y, 2, 2, 0)) return false;
    b.plantTree(x, y, hash2(x, y, 4) < 0.5 ? 0 : 1); return true;
  }, 1400, 2);
  scatter(14, (x, y) => {
    if (!b.areaFree(x, y, 2, 2, 1)) return false;
    b.plantTree(x, y, hash2(x, y, 3) < 0.5 ? 0 : 1); return true;
  }, 900, 3);
  scatter(30, (x, y) => (b.isFree(x, y) ? (b.ground[b.i(x, y)] = gid(TILE.FLOWER_A + Math.floor(rand() * 3)), true) : false), 600, 3);
  scatter(6, (x, y) => (b.areaFree(x, y, 1, 1, 1) ? (b.setDecor(x, y, TILE.ROCK), true) : false), 300, 3);
  scatter(8, (x, y) => (b.areaFree(x, y, 1, 1, 1) ? (b.setDecor(x, y, TILE.BUSH), true) : false), 300, 3);
  scatter(3, (x, y) => (b.areaFree(x, y, 1, 1, 1) ? (b.setDecor(x, y, TILE.STUMP), true) : false), 300, 3);

  // --- townsfolk (flavour only: tips, never fake lab data)
  const npcs: NpcSpec[] = [
    { id: 'student', name: 'Student', sprite: 'npc_1', x: 27, y: 12, facing: 'left', wander: 2, role: 'townsfolk',
      dialog: ['Talk to an agent (Z) to read', 'its real current thought.'] },
    { id: 'postdoc', name: 'Postdoc', sprite: 'npc_2', x: 16, y: 16, facing: 'down', wander: 3, role: 'townsfolk',
      dialog: ['Shift+E shows the event id behind', 'every animation. Nothing here is scripted.'] },
    { id: 'gardener', name: 'Gardener', sprite: 'npc_3', x: 31, y: 24, facing: 'left', wander: 2, role: 'townsfolk',
      dialog: ['When an agent has no task,', 'it naps on this lawn.'] },
  ];
  for (const c of npcs) { b.collide[b.i(c.x, c.y)] = 0; b.decor[b.i(c.x, c.y)] = 0; b.overhead[b.i(c.x, c.y)] = 0; b.occ[b.i(c.x, c.y)] = FREE; }

  const spawn: SpawnSpec = { x: lab.doorX, y: lab.doorY + 1, facing: 'down' };
  finishTerrain(b, spawn);

  const warps: WarpSpec[] = [
    { id: 'warp_lab', x: lab.doorX, y: lab.doorY, to: MAP.lab, spawn: { x: 8, y: 10, facing: 'up' } },
    { id: 'warp_center', x: center.doorX, y: center.doorY, to: MAP.center, spawn: { x: 5, y: 7, facing: 'up' } },
    { id: 'warp_library', x: library.doorX, y: library.doorY, to: MAP.library, spawn: { x: 5, y: 7, facing: 'up' } },
    { id: 'warp_daycare', x: daycare.doorX, y: daycare.doorY, to: MAP.daycare, spawn: { x: 5, y: 7, facing: 'up' } },
    { id: 'warp_pcbox', x: pcbox.doorX, y: pcbox.doorY, to: MAP.pcbox, spawn: { x: 5, y: 7, facing: 'up' } },
    ...CAMPUS_GATES.flatMap((g) => g.tiles.map(([x, y], i) => ({ id: `gate_${g.to}_${i}`, x, y, to: g.to, spawn: townEntrySpawn(gymForTown(g.to)!.entry) }))),
  ];

  // anchors: where agents stand on the campus when their task puts them outside the Lab
  const lawn: Anchor[] = [];
  for (let y = LAWN.y0 + 1; y < LAWN.y1; y += 2) for (let x = LAWN.x0 + 2; x < LAWN.x1 - 1; x += 2) lawn.push({ x, y, facing: 'down' });
  const anchors: Anchors = {
    lawn,
    pokemon_center: [[9, 15], [12, 15], [8, 14], [13, 14], [9, 16]].map(([x, y]) => ({ x, y, facing: 'up' as Dir })),
    library_front: [[36, 15], [39, 15], [35, 16], [40, 16]].map(([x, y]) => ({ x, y, facing: 'up' as Dir })),
    lab_door: [{ x: lab.doorX - 1, y: lab.doorY + 1, facing: 'up' }, { x: lab.doorX + 1, y: lab.doorY + 1, facing: 'up' }],
    dock: [[36, 7], [37, 7]].map(([x, y]) => ({ x, y, facing: 'right' as Dir })),
  };
  for (const g of CAMPUS_GATES) anchors[`gate_${g.to}`] = [{ ...g.arrive }];

  const meta: MapMeta = {
    key: `campus_${theme}`, theme, kind: 'route', title: 'Pallet Campus', width: w, height: h,
    spawn, warps, signs, npcs, trainers: [], exits: [],
  };
  return { key: meta.key, json: toTiled(b, meta), meta, anchors };
}

/* ------------------------------------------------------------------ Oak's Lab ---- */

export const LAB_W = 18;
export const LAB_H = 12;

export function buildLab(theme: RouteTheme = 'bluechip'): LabWorldMap {
  const w = LAB_W, h = LAB_H;
  const b = new Builder(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) b.ground[b.i(x, y)] = gid(((x + y) & 1) === 0 ? TILE.FLOOR_A : TILE.FLOOR_B);

  // walls: top (windows), wall-mounted row, sides, bottom with the door gap (x 8-9)
  for (let x = 0; x < w; x++) b.setDecor(x, 0, x === 4 || x === 13 ? TILE.IWINDOW : TILE.IWALL_TOP);
  for (let x = 0; x < w; x++) b.setDecor(x, 1, TILE.IWALL_MID);
  for (let y = 2; y < h; y++) { b.setDecor(0, y, TILE.IWALL_MID); b.setDecor(w - 1, y, TILE.IWALL_MID); }
  for (let x = 1; x < w - 1; x++) if (x !== 8 && x !== 9) b.setDecor(x, h - 1, TILE.IWALL_MID);

  // library desk: bookshelves, north-west
  for (let x = 1; x <= 3; x++) { b.setDecor(x, 1, TILE.BOOK_T); b.setDecor(x, 2, TILE.BOOK_B); }
  // Pokédex terminal (top half drawn over the wall row)
  b.setOver(5, 1, TILE.DEX_T); b.setDecor(5, 2, TILE.DEX_B);
  // quest board + arena door on the wall
  b.setDecor(7, 1, TILE.QUEST_L); b.setDecor(8, 1, TILE.QUEST_R);
  b.setDecor(10, 1, TILE.ARENA_L); b.setDecor(11, 1, TILE.ARENA_R);
  // server racks, north-east
  for (const x of [14, 15, 16]) { b.setOver(x, 1, TILE.RACK_T); b.setDecor(x, 2, TILE.RACK_B); }
  // code bench: two research desks side by side
  b.setDecor(1, 5, TILE.DESK_L); b.setDecor(2, 5, TILE.DESK_R);
  b.setDecor(4, 5, TILE.DESK_L); b.setDecor(5, 5, TILE.DESK_R);
  // Oak's desk + starter table, centre
  b.setDecor(8, 5, TILE.DESK_L); b.setDecor(9, 5, TILE.DESK_R);
  b.setDecor(11, 5, TILE.BALL_TABLE);
  // analysis table, east
  b.setDecor(14, 6, TILE.ANALYSIS_L); b.setDecor(15, 6, TILE.ANALYSIS_R);
  // scribe desk, south-west
  b.setDecor(3, 8, TILE.SCRIBE);
  // plants
  b.setDecor(1, 10, TILE.PLANT); b.setDecor(16, 10, TILE.PLANT); b.setDecor(16, 4, TILE.PLANT); b.setDecor(12, 9, TILE.PLANT);
  // carpet runner from the door to Oak's desk
  for (let y = 6; y <= 10; y++) { b.ground[b.i(8, y)] = gid(TILE.CARPET_L); b.ground[b.i(9, y)] = gid(TILE.CARPET_R); }
  b.ground[b.i(8, h - 1)] = gid(TILE.EXIT_MAT); b.ground[b.i(9, h - 1)] = gid(TILE.EXIT_MAT);

  const signs: SignSpec[] = [
    { id: 'lab_books', x: 2, y: 2, text: ['Papers the Readers are working through.'] },
    { id: 'lab_dex', x: 5, y: 2, text: ['POKéDEX TERMINAL', 'The lab memory: every run, lesson and fix.'] },
    { id: 'lab_quest', x: 7, y: 1, text: ['QUEST BOARD', "The active project's plan: each card is a real step."] },
    { id: 'lab_arena', x: 10, y: 1, text: ['ARENA DOOR', 'Leads to the Gyms. Battles are live training runs.'] },
    { id: 'lab_racks', x: 15, y: 2, text: ['SERVER RACKS', 'Environment and data prep happen here.'] },
  ];

  const npcs: NpcSpec[] = [
    { id: 'oak', name: 'Prof. Oak', sprite: 'npc_3', x: 8, y: 4, facing: 'down', wander: 0, role: 'townsfolk',
      dialog: ['Welcome to the lab!', 'Every agent here is working on something real.'] },
  ];
  for (const c of npcs) { b.collide[b.i(c.x, c.y)] = 0; b.decor[b.i(c.x, c.y)] = 0; }

  const spawn: SpawnSpec = { x: 8, y: 10, facing: 'up' };
  finishTerrain(b, spawn);

  const back = outsideDoor('lab');
  const warps: WarpSpec[] = [
    { id: 'lab_out_a', x: 8, y: h - 1, to: MAP.campus, spawn: back },
    { id: 'lab_out_b', x: 9, y: h - 1, to: MAP.campus, spawn: back },
  ];

  const A = (pts: Array<[number, number]>, facing: Dir): Anchor[] => pts.map(([x, y]) => ({ x, y, facing }));
  const anchors: Anchors = {
    library_desk: A([[1, 3], [2, 3], [3, 3]], 'up'),
    pokedex: A([[5, 3], [4, 3]], 'up'),
    quest_board: A([[7, 2], [8, 2], [6, 2]], 'up'),
    arena_door: A([[10, 2], [11, 2], [9, 2], [12, 2]], 'up'),
    server_rack: A([[14, 3], [15, 3], [16, 3]], 'up'),
    code_bench: A([[1, 6], [2, 6], [4, 6], [5, 6]], 'up'),
    analysis_table: A([[14, 7], [15, 7], [13, 7], [16, 7]], 'up'),
    scribe_desk: A([[3, 9], [2, 9], [4, 9]], 'up'),
    door: A([[9, 10]], 'up'),
  };

  const meta: MapMeta = {
    key: `lab_${theme}`, theme, kind: 'interior', title: "Prof. Oak's Lab", width: w, height: h,
    spawn, warps, signs, npcs, trainers: [], exits: [],
  };
  return { key: meta.key, json: toTiled(b, meta), meta, anchors };
}
