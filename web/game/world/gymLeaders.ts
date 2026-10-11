/**
 * The four (well, five) real Gym leaders (P9.6/P11.6) — one per paper
 * kit, mirroring the curated claims in brain/pokelab_brain/papers/packs.py
 * by hand (same numbers, same reasoning: TS has no import path into the
 * Python package, so this is a deliberate, small, human-checked mirror,
 * not a duplicate source of truth we forgot to sync).
 */
export interface GymLeader {
  kit: string;
  name: string;
  metricKey: string; // the real job metric this leader's HP is driven by
  targetValue: number; // the real curated claim this run must reach to "win"
  paperTitle: string;
}

export const GYM_LEADERS: GymLeader[] = [
  {
    kit: "grokking",
    name: "Oak's Rival (Grokking)",
    metricKey: "test_acc",
    targetValue: 0.95,
    paperTitle: "Progress Measures for Grokking (Nanda et al., ICLR 2023)",
  },
  {
    kit: "materials",
    name: "Rock-Type Leader (Materials)",
    metricKey: "test_r2",
    targetValue: 0.9,
    paperTitle: "Predicting superconductor critical temperature (Hamidieh, 2018)",
  },
  {
    kit: "distillation",
    name: "Edge Leader (Distillation)",
    metricKey: "distilled_student_acc",
    targetValue: 0.88,
    paperTitle: "Distilling the Knowledge in a Neural Network (Hinton et al., 2015)",
  },
  {
    kit: "nerf",
    name: "Ghost-Type Leader (Tiny NeRF)",
    metricKey: "test_psnr",
    targetValue: 15.0,
    paperTitle: "NeRF (Mildenhall et al., ECCV 2020; Tiny NeRF reduction)",
  },
];

export function leaderFor(kit: string): GymLeader | undefined {
  return GYM_LEADERS.find((l) => l.kit === kit);
}
