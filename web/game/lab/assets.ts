/**
 * The real sprite manifest written by assets/build_atlases.py (§9.6) and how it is loaded into
 * Phaser. Everything here is pre-built on disk (offline-first): animated battle sprites (Showdown),
 * PMD walk/idle/sleep/attack/hurt animations for agents, FireRed overworld humans, trainer
 * portraits and cries.
 */
import type Phaser from 'phaser';

export interface AnimInfo { frameW: number; frameH: number; frames: number; rows: number }
export interface Manifest {
  battle: Record<string, { front: { png: string; json: string; static: string }; back: { png: string; json: string; static: string } }>;
  walk: Record<string, { png: string; json: string; anims: Record<string, AnimInfo>; shadowSize?: number }>;
  people: Record<string, { png: string; json: string; frameW: number; frameH: number; walks: boolean; poses: string[] }>;
  trainers: Record<string, string>;
  cries: Record<string, string>;
  dex: Record<string, number>;
  missing?: string[];
}

export const MANIFEST_KEY = 'pokelab_manifest';
export const MANIFEST_URL = '/assets/gen/manifest.json';

const url = (p: string) => (p.startsWith('/') ? p : `/${p}`);

export const peopleKey = (name: string) => `people_${name}`;
export const walkKey = (species: string) => `walk_${species}`;
export const battleKey = (species: string, side: 'front' | 'back') => `battle_${species}_${side}`;
export const trainerKey = (name: string) => `trainer_${name}`;
export const cryKey = (species: string) => `cry_${species}`;

/** People sheets: the frame order the overworld walking mapping relies on. */
export const PEOPLE_POSES = [
  'down_idle', 'down_walk1', 'down_walk2', 'up_idle', 'up_walk1', 'up_walk2',
  'left_idle', 'left_walk1', 'left_walk2', 'right_idle', 'right_walk1', 'right_walk2',
] as const;

/** grid-engine walkingAnimationMapping for a FireRed people sheet (numeric aliases, see addPeopleAliases). */
export const PEOPLE_WALK_MAPPING = {
  down: { leftFoot: 1, standing: 0, rightFoot: 2 },
  up: { leftFoot: 4, standing: 3, rightFoot: 5 },
  left: { leftFoot: 7, standing: 6, rightFoot: 8 },
  right: { leftFoot: 10, standing: 9, rightFoot: 11 },
} as const;

/** Queue every atlas the overworld needs (battle sprites load lazily in GymScene). */
export function queueOverworldAssets(scene: Phaser.Scene, m: Manifest) {
  for (const [name, p] of Object.entries(m.people)) {
    if (!scene.textures.exists(peopleKey(name))) scene.load.atlas(peopleKey(name), url(p.png), url(p.json));
  }
  for (const [species, wk] of Object.entries(m.walk)) {
    if (!scene.textures.exists(walkKey(species))) scene.load.atlas(walkKey(species), url(wk.png), url(wk.json));
  }
  for (const [name, p] of Object.entries(m.trainers)) {
    if (!scene.textures.exists(trainerKey(name))) scene.load.image(trainerKey(name), url(p));
  }
  for (const [species, p] of Object.entries(m.cries)) {
    if (!scene.cache.audio.exists(cryKey(species))) scene.load.audio(cryKey(species), url(p));
  }
}

/** grid-engine sets frames by number: give each people sheet numeric aliases in PEOPLE_POSES order. */
export function addPeopleAliases(scene: Phaser.Scene, m: Manifest) {
  for (const name of Object.keys(m.people)) {
    const tex = scene.textures.get(peopleKey(name));
    if (!tex || tex.key === '__MISSING' || tex.has('0')) continue;
    PEOPLE_POSES.forEach((pose, i) => {
      const f = tex.get(pose);
      if (f && f.name === pose) tex.add(i, 0, f.cutX, f.cutY, f.cutWidth, f.cutHeight);
    });
  }
}

/** Phaser animations for each PMD species, from the per-frame durations in its atlas. */
export function createAgentAnims(scene: Phaser.Scene, m: Manifest) {
  for (const species of Object.keys(m.walk)) {
    const key = walkKey(species);
    const tex = scene.textures.get(key);
    if (!tex || tex.key === '__MISSING') continue;
    const names = tex.getFrameNames();
    for (const anim of ['walk', 'idle', 'sleep', 'attack', 'hurt']) {
      for (const dir of ['down', 'right', 'up', 'left']) {
        const prefix = `${anim}_${dir}_`;
        let frames = names.filter((n) => n.startsWith(prefix));
        // single-row anims (e.g. sleep) only exist facing down
        if (frames.length === 0) frames = names.filter((n) => n.startsWith(`${anim}_down_`));
        if (frames.length === 0) continue;
        frames.sort((a, b) => Number(a.slice(a.lastIndexOf('_') + 1)) - Number(b.slice(b.lastIndexOf('_') + 1)));
        const animKey = `${species}:${anim}_${dir}`;
        if (scene.anims.exists(animKey)) continue;
        scene.anims.create({
          key: animKey,
          frames: frames.map((frame) => {
            const f = tex.get(frame) as Phaser.Textures.Frame & { customData?: { duration?: number } };
            return { key, frame, duration: f.customData?.duration ?? 120 };
          }),
          repeat: anim === 'attack' || anim === 'hurt' ? 0 : -1,
        });
      }
    }
  }
}
