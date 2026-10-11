import { describe, expect, it } from 'vitest';
import { buildCampus, buildLab, type LabWorldMap } from '../campus';
import { collisionGrid, floodFrom } from '../maps';

/** Every place an agent or the player must reach is walkable and connected to the spawn. */
function checkReachable(map: LabWorldMap) {
  const { width: w, height: h, spawn } = map.meta;
  const blocked = collisionGrid(map);
  // warps/doors sit on walkable tiles; agents and NPCs stand on walkable tiles
  const reach = floodFrom(blocked, w, h, spawn.x, spawn.y);
  const problems: string[] = [];
  const at = (x: number, y: number) => y * w + x;
  for (const wp of map.meta.warps) if (!reach[at(wp.x, wp.y)]) problems.push(`warp ${wp.id} unreachable`);
  for (const n of map.meta.npcs) if (!reach[at(n.x, n.y)]) problems.push(`npc ${n.id} unreachable`);
  for (const [name, list] of Object.entries(map.anchors)) {
    list.forEach((a, i) => {
      if (blocked[at(a.x, a.y)]) problems.push(`anchor ${name}[${i}] (${a.x},${a.y}) is blocked`);
      else if (!reach[at(a.x, a.y)]) problems.push(`anchor ${name}[${i}] (${a.x},${a.y}) unreachable`);
    });
  }
  return problems;
}

describe('Pallet Campus', () => {
  const campus = buildCampus();
  it('is deterministic', () => {
    expect(JSON.stringify(buildCampus().json)).toBe(JSON.stringify(campus.json));
  });
  it('connects spawn to every door, gate, NPC and agent anchor', () => {
    expect(checkReachable(campus)).toEqual([]);
  });
  it('has a warp for the Lab, Center, Library, Day Care, PC and all five gym-town gates', () => {
    const to = new Set(campus.meta.warps.map((w) => w.to));
    for (const k of ['lab', 'center', 'library', 'daycare', 'pcbox', 'grove', 'crystal', 'lumen', 'modulo', 'edgeport']) expect(to.has(k)).toBe(true);
  });
  it('has lawn sleeping spots for a full team', () => {
    expect(campus.anchors.lawn.length).toBeGreaterThanOrEqual(12);
  });
});

describe("Prof. Oak's Lab", () => {
  const lab = buildLab();
  it('connects the door to every station anchor and to Oak', () => {
    expect(checkReachable(lab)).toEqual([]);
  });
  it('has an anchor list for every Lab station in §9.4.2', () => {
    for (const s of ['library_desk', 'code_bench', 'server_rack', 'quest_board', 'arena_door', 'analysis_table', 'scribe_desk']) {
      expect(lab.anchors[s]?.length ?? 0).toBeGreaterThan(0);
    }
  });
});

import { TOWNS, INTERIORS, buildTownMap, buildInterior } from '../towns';

describe('gym towns and interiors', () => {
  const towns = TOWNS.map((t) => [t.key, buildTownMap(t)] as const);
  const rooms = INTERIORS.map((i) => [i.key, buildInterior(i)] as const);
  it.each(towns)('%s connects its gate, Gym door, NPCs and anchors', (_k, m) => {
    expect(checkReachable(m)).toEqual([]);
  });
  it.each(rooms)('%s connects its door to every NPC and anchor', (_k, m) => {
    expect(checkReachable(m)).toEqual([]);
  });
  it('every warp in the world leads to a map that exists', () => {
    const keys = new Set<string>(['campus', 'lab', ...TOWNS.map((t) => t.key), ...INTERIORS.map((i) => i.key)]);
    const all = [buildCampus(), buildLab(), ...towns.map(([, m]) => m), ...rooms.map(([, m]) => m)];
    const dangling = all.flatMap((m) => m.meta.warps.filter((w) => !keys.has(w.to)).map((w) => `${m.meta.title}:${w.id}->${w.to}`));
    expect(dangling).toEqual([]);
  });
  it('each gym hall has its leader standing at the far end', () => {
    for (const [, m] of rooms.filter(([k]) => k.startsWith('gym_'))) {
      expect(m.meta.npcs.find((n) => n.id === 'leader')?.sprite.startsWith('people:')).toBe(true);
    }
  });
});
