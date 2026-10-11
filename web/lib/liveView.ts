/**
 * LIVE adapter for the Lab desk (app/lab): pure functions from the event-folded store (labReducer)
 * to the shapes the desk's panels render. Everything here is derived from real events — when a
 * number does not exist in the log (e.g. GPU-s per agent) it is shown as unknown, never invented.
 * The REPLAY fixture (lib/demo.ts) is only used while labd is not connected.
 */
import type { LabEvent } from './labSocket';
import { levelOf, type AgentViewState, type JobViewState, type LabView, type ProjectViewState } from './labReducer';
import type { AgentStatus, DemoAgent, DemoEvent, DemoQuest, Station } from './demo';
import { ROLES, titleCase } from './roster';
import { gymForKit } from '@/lab/gyms';
import { stationFor } from '@/lab/stations';

/* ------------------------------------------------------------------ agents */

const roleFor = (a: AgentViewState) =>
  ROLES.find((r) => r.title === a.role) ?? ROLES.find((r) => r.line.includes(a.species));

/** Lab-room station for the agent's current task (same rule as lab/placement.ts, in lab-room terms). */
export function deskStation(a: AgentViewState): Station {
  const t = a.currentTask;
  if (!t) return 'lawn';
  const s = stationFor([t.capability]);
  if (s === 'pokemon_center') return 'door'; // on the way out to Nurse Joy
  return s ?? 'quest_board';
}

function statusOf(a: AgentViewState, view: LabView): AgentStatus {
  if (a.currentTask) {
    const thinking = view.recentEvents.find((e) => e.payload.agent_id === a.agentId && (e.kind === 'llm.call_started' || e.kind === 'llm.call_finished'));
    return thinking?.kind === 'llm.call_started' ? 'thinking' : 'working';
  }
  if (a.lastOutcome && !a.lastOutcome.ok) return 'error';
  return 'asleep';
}

/** The agent's latest real words: its newest agent.thought emitted since its current task started. */
function thoughtOf(a: AgentViewState, view: LabView): string {
  if (!a.currentTask) return '';
  const t = view.recentEvents.find((e) => e.kind === 'agent.thought' && e.payload.agent_id === a.agentId && e.seq >= a.currentTask!.seq);
  const text = typeof t?.payload.text === 'string' ? t.payload.text : '';
  return text.slice(0, 140);
}

/**
 * Uncertainty of the agent's posterior. The Selector keeps a Beta posterior per agent; the log carries
 * its mean and the number of rewards, so this is the Beta standard deviation with that many updates.
 */
export function posteriorSigma(mu: number, n: number): number {
  return Math.sqrt((mu * (1 - mu)) / (n + 3));
}

export function liveAgents(view: LabView): DemoAgent[] {
  return Object.values(view.agents)
    .filter((a) => a.status === 'active')
    .sort((x, y) => x.spawnedAtSeq - y.spawnedAtSeq)
    .map((a) => {
      const role = roleFor(a);
      const mu = a.posteriorMean ?? 0.5;
      const line = role?.line ?? [];
      const next = line[line.indexOf(a.species) + 1];
      const task = a.currentTask;
      return {
        id: a.agentId,
        name: a.species,
        role: a.role,
        roleId: role?.id ?? 'spawn',
        version: a.version,
        level: levelOf(a),
        mu,
        sigma: posteriorSigma(mu, a.tasksDone),
        elem: role?.elem ?? 'normal',
        status: statusOf(a, view),
        station: deskStation(a),
        task: task ? task.title || task.capability : a.lastOutcome ? `Idle — last step ${a.lastOutcome.ok ? 'finished' : 'failed'}` : 'Idle — no task',
        thought: thoughtOf(a, view),
        tasks: a.tasksDone,
        cost: 0,
        evolvesTo: next,
      };
    });
}

/* ------------------------------------------------------------------ activity feed */

const num = (v: unknown, d = 3) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : '—');
const str = (v: unknown) => (typeof v === 'string' ? v : '');

function speciesOf(view: LabView, agentId: unknown): string {
  return (typeof agentId === 'string' && view.agents[agentId]?.species) || 'oak';
}

/** One feed row per meaningful event; per-step metrics are summarised by the Experiments panel instead. */
export function feedRow(e: LabEvent, view: LabView): DemoEvent | null {
  const p = e.payload;
  const t = e.ts.slice(11, 19);
  const base = { seq: e.seq, t, kind: e.kind };
  const who = speciesOf(view, p.agent_id);
  const name = titleCase(who);
  switch (e.kind) {
    case 'project.requested':
      return { ...base, who: 'ash', text: `You asked Oak: “${str(p.text)}”`, tone: 'info' };
    case 'project.created':
      return { ...base, who: 'oak', text: `New quest: ${str(p.title)}`, why: `Paper pack “${str(p.paper)}” · kit ${str(p.kit)} · ${(p.plan as unknown[] | undefined)?.length ?? 0} plan steps`, tone: 'info' };
    case 'project.rejected':
      return { ...base, who: 'oak', text: `Oak declined: “${str(p.text)}”`, why: str(p.reason), tone: 'warn' };
    case 'project.completed':
      return { ...base, who: 'oak', text: `Verdict ${str(p.verdict)} — ${str(p.metric)} ${num(p.value)} vs claim ${num(p.claim)}`, why: `job ${str(p.job_id) || '—'} · report ${str(p.report)}`, tone: p.verdict === 'REPRODUCED' ? 'good' : p.verdict === 'PARTIAL' ? 'warn' : 'bad' };
    case 'project.badge_awarded': {
      const g = gymForKit(str(p.kit));
      return { ...base, who: 'ash', text: g ? `${g.badge} earned at ${g.leader}'s Gym!` : 'Badge earned!', why: `${num(p.value)} ≥ claim ${num(p.claim)} (job ${str(p.job_id)})`, tone: 'good' };
    }
    case 'agent.spawned':
      return { ...base, who, text: `${name} joined the team as ${str(p.role) || 'a specialist'}`, why: str(p.reason), tone: 'good' };
    case 'agent.retired':
      return { ...base, who, text: `${name} was sent to Bill's PC`, why: str(p.reason), tone: 'warn' };
    case 'agent.task_started': {
      const cands = (p.candidates as Array<{ agent_id: string; posterior_mean: number }> | undefined) ?? [];
      const why = cands.length > 1
        ? `Thompson draw: ${cands.map((c) => `${titleCase(speciesOf(view, c.agent_id))} ${num(c.posterior_mean, 2)}`).join(' vs ')}`
        : `only agent with capability “${str(p.capability)}”`;
      return { ...base, who, text: `Oak sent out ${name}: ${str(p.title) || str(p.capability)}`, why, tone: 'info' };
    }
    case 'agent.task_finished':
      return { ...base, who, text: `${name} finished ${str(p.step_id)}`, why: p.job_id ? `job ${str(p.job_id)} · checks passed` : 'checks passed', tone: 'good' };
    case 'agent.task_failed':
      return { ...base, who, text: `${name} failed ${str(p.step_id)}`, why: str(p.status) || 'checks failed', tone: 'bad' };
    case 'agent.rewarded': {
      const b = (p.breakdown as Record<string, number> | undefined) ?? {};
      const why = Object.entries(b).map(([k, v]) => `${k} ${num(v, 2)}`).join(' · ');
      return { ...base, who, text: `${name} reward ${num(p.reward, 2)} → level ${Math.round((Number(p.posterior_mean) || 0.5) * 100)}`, why, tone: Number(p.reward) >= 0.7 ? 'good' : 'info' };
    }
    case 'agent.evolved': {
      const ev = (p.evidence as { n?: number; mean_reward?: number } | undefined) ?? {};
      return { ...base, who: str(p.species), text: `${titleCase(str(p.from_species))} evolved into ${titleCase(str(p.species))} (v${num(p.version, 0)})!`, why: `${ev.n} rewarded tasks, mean reward ${num(ev.mean_reward, 2)} · rule: ${str(p.rule)}`, tone: 'good' };
    }
    case 'agent.thought':
      return { ...base, who, text: str(p.text).slice(0, 140), tone: 'info' };
    case 'agent.refine_recommended':
    case 'agent.merge_recommended':
      return { ...base, who, text: `${e.kind === 'agent.refine_recommended' ? 'Refinement' : 'Merge'} recommended for ${name}`, why: str(p.reason), tone: 'warn' };
    case 'job.started':
      return { ...base, who: 'oak', text: `${str(p.job_id)} started (${str(p.kit) || 'job'})`, tone: 'info' };
    case 'job.done': {
      const fin = (p.final as Record<string, unknown> | null) ?? {};
      const g = gymForKit(view.jobs[str(p.job_id)]?.kit);
      const metric = g ? `${g.metricKey} ${num(fin[g.metricKey])}` : '';
      return { ...base, who: 'oak', text: `${str(p.job_id)} ${str(p.status)} ${metric}`.trim(), why: p.error_sig ? `error ${str(p.error_sig)}` : fin.wall_s ? `wall ${num(fin.wall_s, 1)} s on ${str(fin.device)}` : undefined, tone: p.status === 'ok' ? 'good' : 'bad' };
    }
    case 'job.killed':
      return { ...base, who: 'oak', text: `${str(p.job_id)} retreated — “Got away safely!”`, why: str(p.reason), tone: 'good' };
    case 'human.feedback':
      return { ...base, who: 'ash', text: `You rated ${titleCase(speciesOf(view, p.agent_id))} ${num(p.value, 2)}`, tone: 'info' };
    default:
      return null;
  }
}

export function liveFeed(view: LabView, max = 60): DemoEvent[] {
  const out: DemoEvent[] = [];
  for (const e of view.recentEvents) {
    const row = feedRow(e, view);
    if (row) out.push(row);
    if (out.length >= max) break;
  }
  return out;
}

/* ------------------------------------------------------------------ quests */

export function liveQuests(view: LabView): DemoQuest[] {
  return Object.values(view.projects)
    .sort((a, b) => b.createdSeq - a.createdSeq)
    .map((p) => {
      const g = gymForKit(p.kit ?? undefined);
      const done = p.plan.filter((s) => s.status === 'done').length;
      return {
        id: p.projectId,
        title: p.title + (p.verdict ? ` — ${p.verdict}` : ''),
        badge: g ? `${g.leader}'s Gym · ${g.townTitle}${p.badge ? ` · ${g.badge} ✓` : ''}` : (p.paper ?? ''),
        town: g?.townTitle ?? '',
        progress: p.plan.length ? done / p.plan.length : 0,
        steps: p.plan.map((s) => ({
          name: s.title || s.capability,
          agent: s.agentId ? (view.agents[s.agentId]?.species ?? s.agentId) : 'eevee',
          state: s.status === 'done' ? 'done' : s.status === 'running' ? 'running' : s.status === 'failed' ? 'blocked' : 'queued',
        })),
      };
    });
}

/* ------------------------------------------------------------------ experiments + repro */

export interface LiveRun { job: JobViewState; metricKey: string; claim: number | null; floor: number | null; series: Array<{ key: string; points: Array<[number, number]> }> }

/** The job to show: the latest one that has the kit's target metric streaming, else the latest job. */
export function liveRun(view: LabView): LiveRun | null {
  const jobs = Object.values(view.jobs);
  if (!jobs.length) return null;
  const order = (j: JobViewState) => Number(j.jobId.replace(/\D/g, '')) || 0;
  jobs.sort((a, b) => order(b) - order(a));
  const withMetric = jobs.find((j) => { const g = gymForKit(j.kit); return g && (j.metrics[g.metricKey]?.length ?? 0) > 1; });
  const job = withMetric ?? jobs[0];
  const g = gymForKit(job.kit);
  const metricKey = g?.metricKey ?? Object.keys(job.metrics)[0] ?? '';
  const keys = [metricKey, metricKey.replace(/^test_/, 'train_')].filter((k, i, a) => k && a.indexOf(k) === i && job.metrics[k]);
  const series = keys.map((key) => ({ key, points: job.metrics[key].filter((p): p is [number, number] => p[1] !== null) }));
  return { job, metricKey, claim: g?.claim ?? null, floor: g?.floor ?? null, series };
}

export function latestCompleted(view: LabView): ProjectViewState | null {
  return Object.values(view.projects).filter((p) => p.status === 'completed').sort((a, b) => b.createdSeq - a.createdSeq)[0] ?? null;
}

/* ------------------------------------------------------------------ Oak's line + HUD */

/** Oak only "says" what his latest decision event says. */
export function oakLine(view: LabView): string {
  for (const e of view.recentEvents) {
    const p = e.payload;
    switch (e.kind) {
      case 'project.requested': return `A request! “${str(p.text)}” — let me find the right paper pack.`;
      case 'project.created': return `${str(p.title)}: ${(p.plan as unknown[] | undefined)?.length ?? 0} steps. Team, to your stations!`;
      case 'agent.task_started': return `${titleCase(speciesOf(view, p.agent_id))}, I choose you! ${str(p.title) || str(p.capability)}.`;
      case 'project.completed': return p.verdict === 'REPRODUCED'
        ? `Reproduced! ${str(p.metric)} ${num(p.value)} beats the paper's ${num(p.claim)}.`
        : `Verdict: ${str(p.verdict)}. ${str(p.metric)} ${num(p.value)} vs the paper's ${num(p.claim)}.`;
      case 'project.badge_awarded': { const g = gymForKit(str(p.kit)); return g ? `You earned the ${g.badge}!` : 'A badge!'; }
      case 'agent.evolved': return `What's this? ${titleCase(str(p.from_species))} is evolving into ${titleCase(str(p.species))}!`;
      case 'project.rejected': return `Hmm. ${str(p.reason)}`;
    }
  }
  return Object.keys(view.agents).length ? 'The team is ready. Ask me to reproduce a paper!' : '';
}

export interface Telemetry { gpu: { name: string | null; util_pct: number | null; mem_used_mib: number | null; mem_total_mib: number | null } | null }

export function hudStats(view: LabView, tel: Telemetry | null) {
  const jobs = Object.values(view.jobs);
  const g = tel?.gpu;
  return {
    gpu: g?.util_pct ?? null,
    vram: g?.mem_used_mib != null && g.mem_total_mib != null ? `${(g.mem_used_mib / 1024).toFixed(1)} / ${(g.mem_total_mib / 1024).toFixed(0)} GB` : '—',
    jobs: jobs.filter((j) => j.status === 'running').length,
    badges: Object.values(view.projects).filter((p) => p.badge).length,
    agents: Object.values(view.agents).filter((a) => a.status === 'active').length,
  };
}
