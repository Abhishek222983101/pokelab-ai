/**
 * The five gym towns and the small interiors (GAME-DESIGN.md §2). Same PokeStonks `Builder` and
 * theme props as the original routes; content is PokéLab's: each town exists for one paper, its Gym
 * is where that paper's runs are battled, and every sign/NPC line about the science is the curated
 * claim (lab/gyms.ts ↔ brain/pokelab_brain/papers/packs.py), never invented.
 */
import { hash2, hashStr, rng } from '../art/pixel';
import { TILE, gid } from '../art/tileset';
import type { RouteTheme } from '../art/themes';
import { BLOCK, Builder, FREE, KEEP, PATH, toTiled } from './maps';
import type { Dir, MapMeta, NpcSpec, SignSpec, SpawnSpec, WarpSpec } from './mapTypes';
import {
  CAMPUS_GATES, MAP, TOWN_H, TOWN_NORTH_ROAD_X, TOWN_ROAD_Y, TOWN_W, building, finishTerrain, outsideDoor, townEntrySpawn,
  type Anchor, type Anchors, type CampusBuilding, type LabWorldMap,
} from './campus';
import { GYMS, type Gym } from '@/lab/gyms';

/* ------------------------------------------------------------------ towns ---- */

export interface TownSpec extends Gym { key: string; title: string; gymKey: string }

export const TOWNS: TownSpec[] = GYMS.map((g) => ({ ...g, key: g.town, title: g.townTitle, gymKey: `gym_${g.town}` }));

const GYM_X = 16, GYM_Y = 4, GYM_WIDTH = 7, GYM_DOOR_COL = 3;
export const gymDoor = { x: GYM_X + GYM_DOOR_COL, y: GYM_Y + 3 };

export function buildTownMap(t: TownSpec): LabWorldMap {
  const w = TOWN_W, h = TOWN_H;
  const b = new Builder(w, h);
  const rand = rng(hashStr(`town:${t.key}`));
  const theme = t.theme;

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

  // --- roads: plaza in front of the Gym, connector, main street, and the spur to the campus gate
  road(14, 8, 25, 10);
  road(19, 11, 20, TOWN_ROAD_Y);
  road(t.entry === 'w' ? 0 : 3, TOWN_ROAD_Y, t.entry === 'e' ? w - 1 : w - 4, TOWN_ROAD_Y + 1);
  if (t.entry === 'n') road(TOWN_NORTH_ROAD_X, 0, TOWN_NORTH_ROAD_X + 1, TOWN_ROAD_Y);
  if (t.entry === 's') road(19, TOWN_ROAD_Y + 2, 20, h - 1);

  // --- the Gym (marble, slate roof with gold ridge, crest plate) + two houses
  const gym = building(b, GYM_X, GYM_Y, GYM_WIDTH, 'GYM', { roofRows: 2, wallRows: 2, doorCol: GYM_DOOR_COL, plate: TILE.PLATE_CREST });
  keep(GYM_X - 1, GYM_Y - 1, GYM_X + GYM_WIDTH, GYM_Y + 4);
  const hw = building(b, 4, 10, 4, 'HOUSE', { roofRows: 2, wallRows: 1, doorCol: 1 });
  const he = building(b, 32, 10, 4, 'HOUSE', { roofRows: 2, wallRows: 1, doorCol: 2 });
  road(hw.doorX, hw.doorY + 1, hw.doorX, TOWN_ROAD_Y);
  road(he.doorX, he.doorY + 1, he.doorX, TOWN_ROAD_Y);
  keep(3, 9, 8, 13); keep(31, 9, 36, 13);

  // --- signs: real information only
  const signs: SignSpec[] = [];
  const addSign = (id: string, x: number, y: number, text: string[]) => {
    b.occ[b.i(x, y)] = FREE; b.setDecor(x, y, TILE.SIGN); signs.push({ id, x, y, text });
  };
  addSign('sign_gym', 13, 10, [`${t.title.toUpperCase()} GYM`, `Leader: ${t.leader}. Badge: ${t.badge}.`, t.paper]);
  addSign('sign_town', 22, 12, [t.title.toUpperCase(), `Studying: ${t.paper}`]);
  // locked houses read from the walkway (sign on the door tile)
  signs.push({ id: 'house_w', x: hw.doorX, y: hw.doorY, text: ['RESEARCH DORM', 'Locked. Everyone is at the Gym.'] });
  signs.push({ id: 'house_e', x: he.doorX, y: he.doorY, text: ['RESEARCH DORM', 'Locked. Everyone is at the Gym.'] });

  // --- theme props (the PokeStonks theme set: racks, pumpjacks, neon, obelisks, crates)
  const tryTall = (x: number, y: number, top: number, bottom: number) => {
    if (!b.inb(x, y - 1) || !b.isFree(x, y) || !(b.isFree(x, y - 1) || b.occ[b.i(x, y - 1)] === KEEP)) return false;
    b.setOver(x, y - 1, top); b.collide[b.i(x, y - 1)] = 1; b.occ[b.i(x, y - 1)] = BLOCK; b.setDecor(x, y, bottom);
    return true;
  };
  const scatter = (count: number, fn: (x: number, y: number) => boolean, tries = 400, margin = 3) => {
    let placed = 0;
    for (let i = 0; i < tries && placed < count; i++) {
      const x = margin + Math.floor(rand() * (w - margin * 2)), y = margin + Math.floor(rand() * (h - margin * 2));
      if (fn(x, y)) placed++;
    }
  };
  const clearOf = (x: number, y: number, ww: number, hh: number) => b.areaFree(x, y, ww, hh, 1);
  const flank = [[GYM_X - 2, GYM_Y + 3], [GYM_X + GYM_WIDTH + 1, GYM_Y + 3]] as const;
  if (theme === 'tech') {
    for (const [x, y] of flank) tryTall(x, y, TILE.RACK_T, TILE.RACK_B);
    scatter(8, (x, y) => (clearOf(x, y - 1, 1, 2) ? tryTall(x, y, TILE.RACK_T, TILE.RACK_B) : false));
  } else if (theme === 'meme') {
    for (const [x, y] of flank) tryTall(x, y, TILE.ROCKET_T, TILE.ROCKET_B);
    scatter(7, (x, y) => (clearOf(x, y, 1, 1) ? (b.setDecor(x, y, TILE.NEON), true) : false));
  } else if (theme === 'crypto') {
    for (const [x, y] of flank) tryTall(x, y, TILE.OBELISK_T, TILE.OBELISK_B);
    scatter(7, (x, y) => (clearOf(x, y - 1, 1, 2) ? tryTall(x, y, TILE.OBELISK_T, TILE.OBELISK_B) : false));
  } else if (theme === 'energy') {
    scatter(3, (x, y) => {
      if (!clearOf(x, y, 2, 2)) return false;
      b.setOver(x, y, TILE.PUMP_TL); b.setOver(x + 1, y, TILE.PUMP_TR);
      b.collide[b.i(x, y)] = 1; b.collide[b.i(x + 1, y)] = 1; b.occ[b.i(x, y)] = BLOCK; b.occ[b.i(x + 1, y)] = BLOCK;
      b.setDecor(x, y + 1, TILE.PUMP_BL); b.setDecor(x + 1, y + 1, TILE.PUMP_BR);
      return true;
    }, 600, 5);
    scatter(7, (x, y) => (clearOf(x, y, 1, 1) ? (b.setDecor(x, y, TILE.DRUM), true) : false));
  } else if (theme === 'consumer') {
    for (const [x, y] of flank) tryTall(x, y, TILE.LAMP_T, TILE.LAMP_B);
    scatter(9, (x, y) => (clearOf(x, y, 1, 1) ? (b.setDecor(x, y, TILE.CRATE), true) : false));
  }

  // --- tree wall with the campus gate left open
  const gate: Array<[number, number]> =
    t.entry === 'n' ? [[TOWN_NORTH_ROAD_X, 0], [TOWN_NORTH_ROAD_X + 1, 0]]
      : t.entry === 's' ? [[19, h - 1], [20, h - 1]]
        : t.entry === 'w' ? [[0, TOWN_ROAD_Y], [0, TOWN_ROAD_Y + 1]]
          : [[w - 1, TOWN_ROAD_Y], [w - 1, TOWN_ROAD_Y + 1]];
  const plant = (x: number, y: number, v: number) => {
    for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) if (b.path[b.i(x + dx, y + dy)]) return;
    b.plantTree(x, y, v);
  };
  for (let x = 0; x < w; x += 2) { plant(x, 0, (x >> 1) & 1); plant(x, h - 2, ((x >> 1) + 1) & 1); }
  for (let y = 2; y < h - 2; y += 2) { plant(0, y, (y >> 1) & 1); plant(w - 2, y, ((y >> 1) + 1) & 1); }
  scatter(55, (x, y) => {
    const edge = Math.min(x, y, w - 1 - x, h - 1 - y);
    if (edge > 6 || !b.areaFree(x, y, 2, 2, 0)) return false;
    b.plantTree(x, y, hash2(x, y, 4) < 0.5 ? 0 : 1); return true;
  }, 1200, 2);
  scatter(8, (x, y) => (b.areaFree(x, y, 2, 2, 1) ? (b.plantTree(x, y, hash2(x, y, 3) < 0.5 ? 0 : 1), true) : false), 600, 3);
  scatter(24, (x, y) => (b.isFree(x, y) ? (b.ground[b.i(x, y)] = gid(TILE.FLOWER_A + Math.floor(rand() * 3)), true) : false), 500, 3);
  scatter(5, (x, y) => (b.areaFree(x, y, 1, 1, 1) ? (b.setDecor(x, y, TILE.ROCK), true) : false), 300, 3);
  scatter(5, (x, y) => (b.areaFree(x, y, 1, 1, 1) ? (b.setDecor(x, y, TILE.BUSH), true) : false), 300, 3);

  const npcs: NpcSpec[] = [
    { id: 'resident', name: `${t.title} resident`, sprite: 'npc_2', x: 24, y: 13, facing: 'down', wander: 2, role: 'townsfolk',
      dialog: [`${t.leader} defends this claim:`, t.claimText] },
  ];
  for (const c of npcs) { b.collide[b.i(c.x, c.y)] = 0; b.decor[b.i(c.x, c.y)] = 0; b.overhead[b.i(c.x, c.y)] = 0; b.occ[b.i(c.x, c.y)] = FREE; }

  const spawn = townEntrySpawn(t.entry);
  finishTerrain(b, spawn);

  const back = CAMPUS_GATES.find((g) => g.to === t.key)!.arrive;
  const warps: WarpSpec[] = [
    { id: 'gym_door', x: gym.doorX, y: gym.doorY, to: t.gymKey, spawn: { x: 6, y: 11, facing: 'up' } },
    ...gate.map(([x, y], i) => ({ id: `gate_campus_${i}`, x, y, to: MAP.campus, spawn: back })),
  ];
  const A = (pts: Array<[number, number]>, facing: Dir): Anchor[] => pts.map(([x, y]) => ({ x, y, facing }));
  const anchors: Anchors = {
    gym_front: A([[18, 9], [21, 9], [17, 10], [22, 10], [19, 10], [20, 10]], 'up'),
  };
  const meta: MapMeta = {
    key: `town_${t.key}`, theme, kind: 'route', title: t.title, width: w, height: h,
    spawn, warps, signs, npcs, trainers: [], exits: [],
  };
  return { key: meta.key, json: toTiled(b, meta), meta, anchors };
}

/* ------------------------------------------------------------------ interiors ---- */

export interface InteriorSpec {
  key: string;
  title: string;
  theme: RouteTheme;
  kind: 'center' | 'library' | 'daycare' | 'pcbox' | 'gym';
  /** Where walking out puts the player. */
  exitTo: string;
  exitSpawn: SpawnSpec;
  town?: TownSpec;
}

const campusInterior = (key: string, title: string, kind: InteriorSpec['kind'], door: CampusBuilding): InteriorSpec =>
  ({ key, title, theme: 'bluechip', kind, exitTo: MAP.campus, exitSpawn: outsideDoor(door) });

export const INTERIORS: InteriorSpec[] = [
  campusInterior(MAP.center, 'Pokémon Center', 'center', 'center'),
  campusInterior(MAP.library, 'Pokédex Library', 'library', 'library'),
  campusInterior(MAP.daycare, 'Day Care', 'daycare', 'daycare'),
  campusInterior(MAP.pcbox, "Bill's PC", 'pcbox', 'pcbox'),
  ...TOWNS.map((t): InteriorSpec => ({
    key: t.gymKey, title: `${t.title} Gym`, theme: t.theme, kind: 'gym', town: t,
    exitTo: t.key, exitSpawn: { x: gymDoor.x, y: gymDoor.y + 1, facing: 'down' },
  })),
];

/** 12x9 rooms like PokeStonks' Exchange; the Gym hall is 13x13 with the leader at the far end. */
export function buildInterior(spec: InteriorSpec): LabWorldMap {
  const isGym = spec.kind === 'gym';
  const w = isGym ? 13 : 12, h = isGym ? 13 : 9;
  const door = isGym ? [6] : [5, 6];
  const b = new Builder(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) b.ground[b.i(x, y)] = gid(((x + y) & 1) === 0 ? TILE.FLOOR_A : TILE.FLOOR_B);
  for (let x = 0; x < w; x++) { b.setDecor(x, 0, x === 2 || x === w - 3 ? TILE.IWINDOW : TILE.IWALL_TOP); b.setDecor(x, 1, TILE.IWALL_MID); }
  for (let y = 2; y < h; y++) { b.setDecor(0, y, TILE.IWALL_MID); b.setDecor(w - 1, y, TILE.IWALL_MID); }
  for (let x = 1; x < w - 1; x++) if (!door.includes(x)) b.setDecor(x, h - 1, TILE.IWALL_MID);
  for (const x of door) b.ground[b.i(x, h - 1)] = gid(TILE.EXIT_MAT);

  const npcs: NpcSpec[] = [];
  const signs: SignSpec[] = [];
  const anchors: Anchors = {};
  const A = (pts: Array<[number, number]>, facing: Dir): Anchor[] => pts.map(([x, y]) => ({ x, y, facing }));

  switch (spec.kind) {
    case 'center': {
      b.setDecor(3, 3, TILE.COUNTER_L); for (let x = 4; x <= 7; x++) b.setDecor(x, 3, TILE.COUNTER_M); b.setDecor(8, 3, TILE.COUNTER_R);
      for (let y = 4; y <= 8; y++) { b.ground[b.i(5, y)] = gid(TILE.CARPET_L); b.ground[b.i(6, y)] = gid(TILE.CARPET_R); }
      b.ground[b.i(7, 2)] = gid(TILE.HEAL_PAD);
      b.setDecor(1, 2, TILE.PLANT); b.setDecor(10, 2, TILE.PLANT); b.setDecor(1, 7, TILE.PLANT); b.setDecor(10, 7, TILE.PLANT);
      b.setDecor(9, 1, TILE.PLATE_BALL);
      npcs.push({ id: 'nursejoy', name: 'Nurse Joy', sprite: 'people:nursejoy', x: 5, y: 2, facing: 'down', wander: 0, role: 'teller',
        dialog: ['Welcome to the Pokémon Center!', 'Failed runs come here to be triaged.'] });
      anchors.patients = A([[4, 5], [7, 5], [3, 6], [8, 6], [4, 7], [7, 7]], 'up');
      break;
    }
    case 'library': {
      for (let x = 1; x <= 10; x++) if (x !== 5 && x !== 6) b.setDecor(x, 1, TILE.SHELF);
      for (const x0 of [2, 7]) for (let x = x0; x <= x0 + 2; x++) { b.setDecor(x, 3, TILE.BOOK_T); b.setDecor(x, 4, TILE.BOOK_B); }
      b.setOver(10, 5, TILE.DEX_T); b.setDecor(10, 6, TILE.DEX_B);
      b.setDecor(1, 7, TILE.PLANT);
      npcs.push({ id: 'librarian', name: 'Librarian', sprite: 'npc_2', x: 9, y: 6, facing: 'left', wander: 0, role: 'townsfolk',
        dialog: ['Every run the lab ever did is indexed here,', 'so the same experiment never runs twice.'] });
      signs.push({ id: 'lib_dex', x: 10, y: 6, text: ['POKéDEX TERMINAL', 'The lab memory: runs, lessons and fixes.'] });
      anchors.readers = A([[2, 5], [3, 5], [7, 5], [8, 5], [4, 6]], 'up');
      break;
    }
    case 'daycare': {
      for (let y = 3; y <= 6; y++) for (let x = 3; x <= 8; x++) b.ground[b.i(x, y)] = gid(x === 3 ? TILE.CARPET_L : x === 8 ? TILE.CARPET_R : TILE.CARPET_M);
      b.setDecor(1, 2, TILE.PLANT); b.setDecor(10, 2, TILE.PLANT); b.setDecor(1, 7, TILE.PLANT); b.setDecor(10, 7, TILE.PLANT);
      b.setDecor(6, 1, TILE.PLATE_EGG);
      npcs.push({ id: 'daycare_man', name: 'Day-Care Man', sprite: 'npc_1', x: 3, y: 2, facing: 'down', wander: 0, role: 'townsfolk',
        dialog: ['When two agents overlap too much,', 'Prof. Oak merges them here into one.'] });
      npcs.push({ id: 'daycare_lady', name: 'Day-Care Lady', sprite: 'npc_3', x: 8, y: 2, facing: 'down', wander: 0, role: 'townsfolk',
        dialog: ['The merged agent must pass a shadow', 'evaluation before it hatches.'] });
      anchors.pair = A([[5, 4], [6, 4]], 'down');
      break;
    }
    case 'pcbox': {
      b.setDecor(2, 2, TILE.DESK_L); b.setDecor(3, 2, TILE.DESK_R);
      b.setDecor(8, 2, TILE.DESK_L); b.setDecor(9, 2, TILE.DESK_R);
      for (const x of [1, 10]) { b.setOver(x, 4, TILE.RACK_T); b.setDecor(x, 5, TILE.RACK_B); }
      b.setDecor(6, 1, TILE.PLATE_MONITOR);
      npcs.push({ id: 'bill', name: 'Bill', sprite: 'people:bill', x: 6, y: 3, facing: 'down', wander: 0, role: 'townsfolk',
        dialog: ["Hi, I'm Bill! I keep the lab's PC.", 'Retired agents are stored here with their reason.'] });
      break;
    }
    case 'gym': {
      const t = spec.town!;
      for (let y = 3; y <= h - 2; y++) { b.ground[b.i(5, y)] = gid(TILE.CARPET_L); b.ground[b.i(6, y)] = gid(TILE.CARPET_M); b.ground[b.i(7, y)] = gid(TILE.CARPET_R); }
      b.ground[b.i(6, 2)] = gid(TILE.HEAL_PAD);
      for (const y of [4, 7, 10]) for (const x of [2, 10]) { b.setOver(x, y - 1, TILE.OBELISK_T); b.setDecor(x, y, TILE.OBELISK_B); }
      b.setDecor(1, h - 2, TILE.PLANT); b.setDecor(w - 2, h - 2, TILE.PLANT);
      b.setDecor(6, 1, TILE.PLATE_CREST);
      npcs.push({ id: 'leader', name: t.leader, sprite: `people:${t.leaderSprite}`, x: 6, y: 3, facing: 'down', wander: 0, role: 'teller',
        dialog: [`I am ${t.leader}. My claim:`, t.claimText, `Reproduce it and the ${t.badge} is yours.`] });
      signs.push({ id: 'gym_plate', x: 6, y: 1, text: [`${t.title.toUpperCase()} GYM`, t.paper] });
      anchors.challenger = A([[6, 9], [5, 9], [7, 9]], 'up');
      break;
    }
  }
  for (const c of npcs) { b.collide[b.i(c.x, c.y)] = 0; b.decor[b.i(c.x, c.y)] = 0; }

  const spawn: SpawnSpec = isGym ? { x: 6, y: 11, facing: 'up' } : { x: 5, y: 7, facing: 'up' };
  finishTerrain(b, spawn);
  const warps: WarpSpec[] = door.map((x, i) => ({ id: `out_${i}`, x, y: h - 1, to: spec.exitTo, spawn: spec.exitSpawn }));
  const meta: MapMeta = {
    key: `int_${spec.key}`, theme: spec.theme, kind: 'interior', title: spec.title, width: w, height: h,
    spawn, warps, signs, npcs, trainers: [], exits: [],
  };
  return { key: meta.key, json: toTiled(b, meta), meta, anchors };
}
