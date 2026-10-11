/**
 * REPLAY fixture — a hand-written slice of a lab session used when labd is not connected (§2.2 P6 "fail soft").
 * The UI labels everything built from this file as REPLAY. It is never presented as live, and none of these
 * numbers may appear on a slide: only `[MEASURED]` values from var/reports/*.json may (§1 rule 3).
 */
import type { Elem } from '@/app/components/ui';

export type AgentStatus = 'idle' | 'working' | 'thinking' | 'error' | 'asleep';
export type Station = 'library_desk' | 'code_bench' | 'server_rack' | 'quest_board' | 'arena_door' | 'analysis_table' | 'scribe_desk' | 'lawn' | 'door';

export interface DemoAgent {
  id: string;
  name: string; // current species
  role: string;
  roleId: string;
  version: number;
  level: number;
  mu: number; // posterior mean reward
  sigma: number;
  elem: Elem;
  status: AgentStatus;
  station: Station;
  task: string;
  thought: string;
  tasks: number;
  cost: number; // GPU-seconds
  evolvesTo?: string;
}

export const DEMO_AGENTS: DemoAgent[] = [
  { id: 'a-reader', name: 'pikachu', role: 'Paper Reader', roleId: 'reader', version: 2, level: 64, mu: 0.81, sigma: 0.05, elem: 'electric', status: 'working', station: 'library_desk',
    task: 'Extract claims from “Grokking” (Power et al. 2022)', thought: 'Claim 3: modular addition generalises after ~10k steps at 30 % train fraction.', tasks: 41, cost: 12 },
  { id: 'a-impl', name: 'charmeleon', role: 'Implementer', roleId: 'implementer', version: 2, level: 63, mu: 0.76, sigma: 0.06, elem: 'fire', status: 'thinking', station: 'code_bench',
    task: 'Implement 1-layer transformer on mod-97 addition', thought: 'AdamW β2=0.98, wd=1.0 per the paper’s appendix — checking config hash first.', tasks: 37, cost: 88, evolvesTo: 'charizard' },
  { id: 'a-env', name: 'ivysaur', role: 'Environment Engineer', roleId: 'env', version: 2, level: 58, mu: 0.72, sigma: 0.07, elem: 'grass', status: 'working', station: 'server_rack',
    task: 'Resolve torch 2.14 + cu130 in project venv', thought: 'uv resolved in 4.1 s; warm worker w-gpu-0 reused.', tasks: 29, cost: 31 },
  { id: 'a-debug', name: 'squirtle', role: 'Debugger', roleId: 'debugger', version: 1, level: 41, mu: 0.66, sigma: 0.11, elem: 'water', status: 'asleep', station: 'lawn',
    task: 'Idle — nothing failing', thought: '', tasks: 12, cost: 9 },
  { id: 'a-analyst', name: 'kadabra', role: 'Analyst', roleId: 'analyst', version: 2, level: 69, mu: 0.88, sigma: 0.04, elem: 'psychic', status: 'working', station: 'analysis_table',
    task: 'ReproComparator: ours 19.8k steps vs paper ~10k', thought: 'Hypothesis H1 seed variance: measured ±3.1k over 5 seeds — explains 31 % of the gap.', tasks: 33, cost: 5 },
  { id: 'a-exp', name: 'porygon', role: 'Experimenter', roleId: 'experimenter', version: 1, level: 52, mu: 0.69, sigma: 0.08, elem: 'normal', status: 'thinking', station: 'quest_board',
    task: 'What-if: weight-decay 0 → does grokking vanish?', thought: 'Navigator suggests wd∈{0, 0.1, 1.0} × data-frac∈{0.3, 0.5}: 6 runs, Oracle prunes losers.', tasks: 24, cost: 44 },
  { id: 'a-run', name: 'magneton', role: 'Compute Runner', roleId: 'runner', version: 2, level: 47, mu: 0.7, sigma: 0.09, elem: 'electric', status: 'working', station: 'arena_door',
    task: 'job #12 on local GPU (pred 14 s)', thought: 'Router: local beats Kaggle queue by 41 s.', tasks: 51, cost: 160 },
  { id: 'a-scribe', name: 'hoothoot', role: 'Scribe', roleId: 'scribe', version: 1, level: 28, mu: 0.6, sigma: 0.14, elem: 'normal', status: 'idle', station: 'scribe_desk',
    task: 'Waiting for the evidence table', thought: '', tasks: 8, cost: 2 },
  { id: 'a-eevee', name: 'eevee', role: 'Spawned specialist', roleId: 'spawn', version: 1, level: 5, mu: 0.5, sigma: 0.25, elem: 'normal', status: 'idle', station: 'door',
    task: 'Proposed: “Fourier-analysis” specialist (skill gap detected)', thought: 'Waiting for approval from the researcher.', tasks: 0, cost: 0 },
];

export interface DemoEvent { seq: number; t: string; kind: string; who: string; text: string; why?: string; tone?: 'good' | 'bad' | 'warn' | 'info' }

export const DEMO_FEED: DemoEvent[] = [
  { seq: 1042, t: '12:04:18', kind: 'agent.spawn_proposed', who: 'eevee', text: 'A wild Eevee appeared — skill gap: fourier_analysis', why: 'Scout coverage 0.34 < 0.60 for capability “fourier_analysis”', tone: 'warn' },
  { seq: 1041, t: '12:04:11', kind: 'job.metric', who: 'magneton', text: 'job #12 · test_acc 0.97 (+0.31 in 400 steps)', why: 'It’s super effective — jump > 3× rolling mean', tone: 'good' },
  { seq: 1040, t: '12:03:58', kind: 'ml.navigator_updated', who: 'porygon', text: 'Safari map: fog lifted at wd=0.1 × frac=0.5', why: 'GP posterior σ dropped 0.42 → 0.19', tone: 'info' },
  { seq: 1039, t: '12:03:40', kind: 'job.killed', who: 'magneton', text: 'job #11 retreated — “Got away safely!”', why: 'Oracle P(success)=0.03 for 3 checks, 38 % progress · saved 41 GPU-s', tone: 'good' },
  { seq: 1038, t: '12:03:22', kind: 'oak.selection', who: 'oak', text: 'Sent out Charmeleon for capability “implement”', why: 'Thompson draw: Charmeleon 0.81 vs Charmander 0.62 vs Eevee 0.50', tone: 'info' },
  { seq: 1037, t: '12:03:02', kind: 'agent.rewarded', who: 'kadabra', text: 'Kadabra +0.88 — repro verdict PARTIAL with evidence', why: 'quality 0.92 · success 1.0 · cost 0.3 · human 👍', tone: 'good' },
  { seq: 1036, t: '12:02:44', kind: 'memory.hit', who: 'oak', text: 'Found in the Pokédex — run #7 (same config hash)', why: 'config_hash 9f3a… · skipped 62 s of GPU', tone: 'info' },
  { seq: 1035, t: '12:02:20', kind: 'agent.task_failed', who: 'charmeleon', text: 'CUDA OOM at batch 512 → Nurse Joy routed a fix', why: 'Medic recalled fix #3: halve batch, keep LR·√ratio', tone: 'bad' },
  { seq: 1034, t: '12:01:55', kind: 'oak.capability_analysis', who: 'oak', text: 'Task needs: paper_read · implement · run_experiment · analyze', why: 'Project “Reproduce Grokking” — taxonomy-constrained LLM + coverage check', tone: 'info' },
];

export interface DemoQuest { id: string; title: string; badge: string; progress: number; steps: Array<{ name: string; agent: string; state: 'done' | 'running' | 'queued' | 'blocked' }>; town: string }

export const DEMO_QUESTS: DemoQuest[] = [
  { id: 'q1', title: 'Reproduce “Grokking” (Power et al.)', badge: 'Sabrina’s Gym · Modulo City', progress: 0.62, town: 'Modulo City',
    steps: [
      { name: 'Read paper & extract claims', agent: 'pikachu', state: 'done' },
      { name: 'Set up env (torch 2.14)', agent: 'ivysaur', state: 'done' },
      { name: 'Implement transformer + data', agent: 'charmeleon', state: 'running' },
      { name: 'Run baseline (3 seeds)', agent: 'magneton', state: 'running' },
      { name: 'What-if: weight decay sweep', agent: 'porygon', state: 'queued' },
      { name: 'Compare to paper & explain gap', agent: 'kadabra', state: 'queued' },
      { name: 'Write report', agent: 'hoothoot', state: 'blocked' },
    ] },
  { id: 'q2', title: 'Distil a small model (Hinton et al.)', badge: 'Lt. Surge’s Gym · Edge Port', progress: 0.18, town: 'Edge Port',
    steps: [
      { name: 'Read paper & extract claims', agent: 'pikachu', state: 'done' },
      { name: 'Train teacher', agent: 'magneton', state: 'running' },
      { name: 'Distil student', agent: 'charmeleon', state: 'queued' },
    ] },
];

/** Deterministic grokking-shaped curves (fixture): train saturates early, test jumps late. */
export function demoCurves(n = 120) {
  const train: number[] = [], test: number[] = [], forecast: number[] = [];
  for (let i = 0; i < n; i++) {
    const x = i / (n - 1);
    train.push(1 - Math.exp(-x * 14));
    const s = 1 / (1 + Math.exp(-(x - 0.62) * 22));
    test.push(0.04 + 0.93 * s + 0.012 * Math.sin(i * 1.7));
    forecast.push(0.04 + 0.93 / (1 + Math.exp(-(x - 0.6) * 18)));
  }
  return { train, test, forecast };
}

export const DEMO_HUD = { gpu: 71, vram: '4.1 / 8 GB', jobs: 3, approvals: 1, tokens: '612k', saved: '41 GPU-s' };
