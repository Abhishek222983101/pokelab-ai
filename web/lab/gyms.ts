/**
 * The five Gyms (SYSTEM-ARCHITECTURE §2.4/§2.5, GAME-DESIGN §2/§5): one town, one leader, one paper
 * kit each. The claim numbers mirror the curated PaperPacks in brain/pokelab_brain/papers/packs.py
 * by hand (TS has no import path into the Python package) — a small, human-checked table; the
 * acceptance suite's evidence for AC-4 cites the same packs.
 */
/** The PokeStonks route themes (game/art/themes.ts), repeated so lab/ never depends on game/. */
export type RouteTheme = 'tech' | 'bluechip' | 'energy' | 'meme' | 'consumer' | 'crypto';

export type TownKey = 'modulo' | 'edgeport' | 'lumen' | 'crystal' | 'grove';

export interface Gym {
  town: TownKey;
  townTitle: string;
  theme: RouteTheme;
  /** Which edge of the town map the gate back to Pallet Campus is on. */
  entry: 'n' | 's' | 'e' | 'w';
  leader: string;          // display name
  leaderSprite: string;    // FireRed people sheet + Showdown portrait name
  ace: string;             // leader's Pokémon (Showdown battle sprite)
  badge: string;
  kit: string;             // workers kit that runs this gym's battles
  paper: string;
  /** The job metric the leader's "gap HP" is computed from, and the curated claim. */
  metricKey: string;
  claim: number;
  /** The metric's real starting point (chance / measured baseline): HP is measured from here. */
  floor: number;
  better: 'higher' | 'lower';
  claimText: string;
}

export const GYMS: Gym[] = [
  {
    town: 'modulo', townTitle: 'Modulo City', theme: 'tech', entry: 'n',
    leader: 'Sabrina', leaderSprite: 'sabrina', ace: 'alakazam', badge: 'Marsh Badge',
    kit: 'grokking', paper: 'Progress Measures for Grokking (Nanda et al., ICLR 2023)',
    metricKey: 'test_acc', claim: 0.95, floor: 1 / 113, better: 'higher',
    claimText: 'A 1-layer transformer on addition mod 113 groks: test accuracy reaches 95%.',
  },
  {
    town: 'edgeport', townTitle: 'Edge Port', theme: 'energy', entry: 'n',
    leader: 'Lt. Surge', leaderSprite: 'ltsurge', ace: 'raichu', badge: 'Thunder Badge',
    kit: 'distillation', paper: 'Distilling the Knowledge in a Neural Network (Hinton et al., 2015)',
    metricKey: 'distilled_student_acc', claim: 0.88, floor: 0.1, better: 'higher',
    claimText: 'A 16-unit student taught with soft labels beats the same student on hard labels.',
  },
  {
    town: 'lumen', townTitle: 'Lumen Town', theme: 'meme', entry: 'w',
    leader: 'Blaine', leaderSprite: 'blaine', ace: 'arcanine', badge: 'Volcano Badge',
    kit: 'nerf', paper: 'NeRF (Mildenhall et al., ECCV 2020) — Tiny NeRF reduction',
    metricKey: 'test_psnr', claim: 15.0, floor: 9.6, better: 'higher',
    claimText: 'A positional-encoded MLP renders a held-out view of the lego scene at 15 dB PSNR.',
  },
  {
    town: 'crystal', townTitle: 'Crystal Cave', theme: 'crypto', entry: 'e',
    leader: 'Brock', leaderSprite: 'brock', ace: 'onix', badge: 'Boulder Badge',
    kit: 'materials', paper: 'Superconductor critical temperature (Hamidieh, 2018)',
    metricKey: 'test_r2', claim: 0.9, floor: 0, better: 'higher',
    claimText: 'Gradient boosting predicts superconductor Tc with test R^2 of 0.90.',
  },
  {
    town: 'grove', townTitle: 'Arena Grove', theme: 'consumer', entry: 's',
    leader: 'Erika', leaderSprite: 'erika', ace: 'vileplume', badge: 'Rainbow Badge',
    kit: 'arena', paper: 'Why do tree-based models still outperform deep learning on tabular data? (Grinsztajn et al., 2022)',
    metricKey: 'tree_fold_acc', claim: 0.84, floor: 0.5, better: 'higher',
    claimText: 'On real tabular data, trees match or beat an MLP; with noise features, significantly.',
  },
];

export const gymForKit = (kit: string | undefined) => GYMS.find((g) => g.kit === kit);
export const gymForTown = (town: string) => GYMS.find((g) => g.town === town);

/**
 * Leader's remaining "gap HP" in [0, 1]: 1 = still at the metric's real floor (chance / measured
 * baseline), 0 = the paper's claim reached. Exact and monotonic — the battle never animates progress
 * the metric didn't make.
 */
export function gapHp(gym: Gym, value: number | null | undefined): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 1;
  const span = gym.claim - gym.floor;
  const remaining = gym.better === 'higher' ? gym.claim - value : value - gym.claim;
  return Math.max(0, Math.min(1, remaining / Math.abs(span)));
}
