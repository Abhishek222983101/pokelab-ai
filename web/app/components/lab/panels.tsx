'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { DEMO_QUESTS, demoCurves, type DemoAgent, type DemoEvent, type DemoQuest } from '@/lib/demo';
import type { LiveRun } from '@/lib/liveView';
import type { ExploreView, JobViewState, PaperView, ProjectViewState } from '@/lib/labReducer';
import type { LabEvent } from '@/lib/labSocket';
import { gymForKit } from '@/lab/gyms';
import { EEVEE_FORMS, ELEM_COLOR, ROLES, titleCase, trainerPortrait } from '@/lib/roster';
import { Mon } from '../Mon';
import { Button, Chip, Panel, StatBar, StatusChip, cx } from '../ui';

/* ------------------------------------------------------------------ shared bits */

export const SectionTitle = ({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) => (
  <div className="mb-2 flex items-center justify-between gap-2">
    <h3 className="font-pixel t-10 m-0 text-navy">{children}</h3>
    {right}
  </div>
);

const toneChip: Record<NonNullable<DemoEvent['tone']>, string> = { good: 'chip-good', bad: 'chip-bad', warn: 'chip-electric', info: 'chip-plain' };

export const levelOf = (a: DemoAgent) => a.level;
export const labelOf = (a: DemoAgent) => `${titleCase(a.name)} Lv${a.level}`;

/* ------------------------------------------------------------------ Team */

export function TeamPanel({ agents, selected, onSelect }: { agents: DemoAgent[]; selected: string | null; onSelect: (id: string) => void }) {
  const active = agents.filter((a) => a.status !== 'asleep').length;
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">{active} AWAKE · {agents.length} ON TEAM</span>}>TEAM</SectionTitle>
      <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2">
        {agents.map((a) => (
          <li key={a.id}>
            <button
              type="button"
              onClick={() => onSelect(a.id)}
              aria-pressed={selected === a.id}
              className="tile !m-0 !w-full !flex-row !items-center !justify-start !gap-3 !px-3 !py-2 text-left"
              style={{ ['--t' as string]: ELEM_COLOR[a.elem], minHeight: 84 }}
              aria-checked={selected === a.id}
              role="checkbox"
            >
              <Mon species={a.name} size={64} />
              <span className="min-w-0 flex-1">
                <span className="block font-pixel t-8 leading-[1.5]">{titleCase(a.name)} <span className="text-slate">v{a.version}</span></span>
                <span className="block font-body text-[12px] font-normal leading-tight text-slate" style={{ fontFamily: 'var(--font-body)' }}>{a.role}</span>
                <span className="mt-1 flex items-center gap-1"><StatusChip status={a.status} /><span className="font-pixel t-8">Lv{a.level}</span></span>
                <span className="mt-1 block"><StatBar label="XP" value={Math.round(a.mu * 100)} max={100} color={ELEM_COLOR[a.elem]} display={`${Math.round(a.mu * 100)}`} /></span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ Inspector (what · why · how well · history) */

export function Inspector({ agent, onClose, onApprove, onReject, approved, onFeedback }: { agent: DemoAgent; onClose: () => void; onApprove: () => void; onReject: () => void; approved: boolean; onFeedback?: (value: number) => void }) {
  const role = ROLES.find((r) => r.id === agent.roleId);
  // Eevee is the one branching line: it specialises into five forms depending on the skill gap it fills.
  const line = agent.name === 'eevee' ? ['eevee', ...EEVEE_FORMS] : (role?.line ?? [agent.name]);
  const idx = line.indexOf(agent.name);
  const proposed = agent.id === 'a-eevee' && !approved;
  return (
    <Panel tone="dialog" className="!m-0" aria-label={`${agent.name} details`}>
      <div className="flex items-start gap-3">
        <div className="relative flex h-24 w-24 flex-none items-end justify-center bg-navy-deep" style={{ boxShadow: '0 0 0 3px var(--color-gold)' }}>
          <Mon species={agent.name} size={88} shadow />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-pixel t-12 m-0 text-yellow">{titleCase(agent.name)}</p>
          <p className="m-0 text-[14px] text-cream/80">{agent.role} · v{agent.version} · Lv {agent.level}</p>
          <div className="mt-1 flex flex-wrap items-center"><Chip kind={agent.elem}>{agent.elem}</Chip><StatusChip status={agent.status} /></div>
        </div>
        <Button variant="quiet" small icon aria-label="Close inspector" onClick={onClose}>✕</Button>
      </div>

      <dl className="mt-3 grid gap-2 text-[14px]">
        <div><dt className="font-pixel t-8 text-yellow">DOING</dt><dd className="m-0">{agent.task}</dd></div>
        {agent.thought && <div><dt className="font-pixel t-8 text-yellow">THINKING</dt><dd className="m-0 italic text-cream/90">“{agent.thought}”</dd></div>}
      </dl>

      <div className="hud-bar mt-3 grid gap-1 bg-navy-deep p-2">
        <StatBar label="REWARD" value={Math.round(agent.mu * 100)} max={100} color="#58d858" display={agent.mu.toFixed(2)} />
        <StatBar label="CERTAIN" value={Math.round((1 - agent.sigma * 2) * 100)} max={100} color="#94c6fc" display={`±${agent.sigma.toFixed(2)}`} />
        <StatBar label="TASKS" value={agent.tasks} max={60} color="#f8d858" />
        {!onFeedback && <StatBar label="GPU-s" value={agent.cost} max={200} color="#f08030" />}
      </div>

      <p className="font-pixel t-8 mb-1 mt-3 text-yellow">LINEAGE</p>
      <div className="flex flex-wrap items-end gap-1">
        {line.map((s, i) => (
          <div key={s} className="flex items-end gap-1">
            <div className={cx('p-1', i === idx ? 'bg-yellow' : 'bg-navy-deep opacity-70', i > idx && agent.name === 'eevee' && 'opacity-90')} title={i <= idx ? `${titleCase(s)} (reached)` : `${titleCase(s)} (locked — needs a measured improvement)`}>
              <Mon species={s} size={i === idx ? 52 : 40} className={i > idx ? 'brightness-0 opacity-60' : ''} />
            </div>
            {i < line.length - 1 && agent.name !== 'eevee' && <i aria-hidden="true" className="mb-5 block h-3 w-2 bg-cream/70" style={{ clipPath: 'polygon(0 0,100% 50%,0 100%)' }} />}
          </div>
        ))}
      </div>
      {agent.history && (
        <div className="mt-3">
          <p className="font-pixel t-8 mb-1 text-yellow">WHAT IT CARRIES INTO THE NEXT PROJECT</p>
          <p className="m-0 mb-2 text-[13px] leading-snug text-cream/80">
            Oak picks this agent by sampling its reward posterior (mean {agent.mu.toFixed(2)} ± {agent.sigma.toFixed(2)} from {agent.tasks} rewarded tasks). Every task below was logged with its reward, so the next selection starts from this record.
          </p>
          {agent.lineage && agent.lineage.length > 0 && (
            <ul className="m-0 mb-2 list-none p-0 text-[13px]">
              {agent.lineage.map((l) => (
                <li key={l.seq} className="text-cream/90"><b className="font-pixel t-8 text-yellow">{l.kind === 'evolved' ? 'EVOLVED' : 'DE-EVOLVED'} #{l.seq}</b> {titleCase(l.from)} → {titleCase(l.to)} (v{l.version}) · {l.note}</li>
              ))}
            </ul>
          )}
          <p className="font-pixel t-8 mb-1 text-yellow">WORK LOG ({agent.history.length})</p>
          {agent.history.length === 0 && <p className="m-0 text-[13px] text-cream/70">No tasks logged this session.</p>}
          <ol className="m-0 grid max-h-72 list-none gap-2 overflow-auto p-0">
            {agent.history.slice(0, 12).map((h) => (
              <li key={`${h.seq}`} className="bg-navy-deep p-2 text-[13px] leading-snug">
                <span className="flex flex-wrap items-center gap-x-2">
                  <span className={cx('chip', h.status === 'done' ? 'chip-good' : h.status === 'failed' ? 'chip-bad' : 'chip-water')}>{h.status}</span>
                  <span className="font-pixel t-8 text-cream/70">#{h.seq} · {h.capability}{h.jobId ? ` · ${h.jobId}` : ''}{h.reward !== null ? ` · reward ${h.reward.toFixed(2)}` : ''}</span>
                </span>
                <span className="block text-cream">{h.title}</span>
                {h.thoughts.map((t, i) => <span key={i} className="block text-cream/80">› {t}</span>)}
              </li>
            ))}
          </ol>
        </div>
      )}
      {agent.evolvesTo && <p className="mt-1 text-[13px] text-cream/80">Evolves to {titleCase(agent.evolvesTo)} when its shadow run beats v{agent.version} by a margin.</p>}

      {onFeedback && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="font-pixel t-8 text-yellow">RATE ITS LAST WORK</span>
          <Button small onClick={() => onFeedback(1)}>👍 good</Button>
          <Button small variant="secondary" onClick={() => onFeedback(0)}>👎 bad</Button>
        </div>
      )}

      {proposed && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button small onClick={onApprove}>Throw Poké Ball (approve)</Button>
          <Button small variant="secondary" onClick={onReject}>Send away</Button>
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ Activity */

function relatedEvents(raw: LabEvent, events: LabEvent[]): LabEvent[] {
  const p = raw.payload;
  const job = typeof p.job_id === 'string' ? p.job_id : null;
  const step = typeof p.step_id === 'string' ? p.step_id : null;
  const proj = typeof p.project_id === 'string' ? p.project_id : raw.project;
  return events.filter((e) => e.seq !== raw.seq && (
    (job && e.payload.job_id === job) || (step && proj && e.payload.step_id === step && (e.payload.project_id === proj || e.project === proj))
  )).sort((x, y) => x.seq - y.seq);
}

export function ActivityPanel({ feed, onFocus, events = [] }: { feed: DemoEvent[]; onFocus: (who: string) => void; events?: LabEvent[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">CLICK A ROW FOR ITS PROOF</span>}>ACTIVITY</SectionTitle>
      <ol className="m-0 grid list-none gap-2 p-0">
        {feed.map((e) => {
          const isOpen = open === e.seq && !!e.raw;
          const rel = isOpen && e.raw ? relatedEvents(e.raw, events) : [];
          const metricPts = rel.filter((r) => r.kind === 'job.metric').length;
          return (
            <li key={e.seq} className="feed-row">
              <button type="button" className="flex w-full items-start gap-2 bg-transparent p-0 text-left" onClick={() => setOpen(isOpen ? null : e.seq)} aria-expanded={isOpen}>
                {e.who === 'oak' || e.who === 'ash' ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={trainerPortrait(e.who)} alt="" width={36} height={36} style={{ imageRendering: 'pixelated', width: 36, height: 36, objectFit: 'contain' }} />
                ) : (
                  <Mon species={e.who} size={36} />
                )}
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2">
                    <span className={cx('chip', toneChip[e.tone ?? 'info'])}>{e.kind}</span>
                    <span className="font-pixel t-8 text-slate tabular-nums">#{e.seq} · {e.t}</span>
                    {e.raw && <span className="font-pixel t-8 text-navy">{isOpen ? '▲ HIDE PROOF' : '▼ PROOF'}</span>}
                  </span>
                  <span className="mt-0.5 block text-[15px] leading-snug text-ink">{e.text}</span>
                  {e.why && <span className="block text-[13px] leading-snug text-slate"><b className="font-pixel t-8 text-navy">WHY </b>{e.why}</span>}
                </span>
              </button>
              {isOpen && e.raw && (
                <div className="mt-2 bg-navy-deep p-2 text-cream">
                  <p className="font-pixel t-8 m-0 mb-1 text-yellow">THE LOGGED EVENT (labd event store, var/lab.db)</p>
                  <pre className="m-0 max-h-56 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-snug">{JSON.stringify({ seq: e.raw.seq, ts: e.raw.ts, kind: e.raw.kind, actor: e.raw.actor, project: e.raw.project, payload: e.raw.payload }, null, 2).slice(0, 3000)}</pre>
                  {(rel.length > 0) && (
                    <div className="mt-2">
                      <p className="font-pixel t-8 m-0 mb-1 text-yellow">RELATED EVENTS ({rel.length}{metricPts ? `, incl. ${metricPts} job.metric points` : ''})</p>
                      <div className="flex flex-wrap gap-1">
                        {rel.filter((r) => r.kind !== 'job.metric').slice(0, 14).map((r) => <span key={r.seq} className="chip chip-plain">#{r.seq} {r.kind}</span>)}
                      </div>
                    </div>
                  )}
                  <div className="mt-2 flex gap-2"><Button small variant="secondary" onClick={() => onFocus(e.who)}>Open agent</Button></div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ Quests (plan DAG as a checklist) */

export function QuestsPanel({ quests }: { quests?: DemoQuest[] }) {
  const list = quests ?? DEMO_QUESTS;
  return (
    <div>
      <SectionTitle right={quests ? undefined : <span className="font-pixel t-8 text-slate">REPLAY</span>}>QUESTS</SectionTitle>
      {quests && list.length === 0 && <p className="m-1 text-[14px] text-slate">No quests yet. Ask Oak to reproduce a paper (box below the lab).</p>}
      <div className="grid gap-4">
        {list.map((q) => (
          <Panel key={q.id} tone="well" className="!m-1">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-pixel t-10 m-0 leading-[1.6] text-navy">{q.title}</p>
                <p className="m-0 text-[13px] text-slate">{q.badge}</p>
              </div>
              <span className="font-pixel t-12 tabular-nums">{Math.round(q.progress * 100)}%</span>
            </div>
            <div className="bar mt-2"><i style={{ width: `${q.progress * 100}%`, ['--bar' as string]: '#58d858' }} /></div>
            <ol className="m-0 mt-3 grid list-none gap-1 p-0">
              {q.steps.map((s, i) => (
                <li key={i} className="flex items-center gap-2 text-[14px]">
                  <span aria-hidden="true" className="font-pixel t-10 w-4 text-center" style={{ color: s.state === 'done' ? '#1f8f2a' : s.state === 'running' ? '#2d57d6' : '#7878a8' }}>
                    {s.state === 'done' ? '✓' : s.state === 'running' ? '▶' : s.state === 'blocked' ? '■' : '·'}
                  </span>
                  {s.agent ? <Mon species={s.agent} size={28} /> : <span className="inline-block w-7" />}
                  <span className={cx('flex-1', s.state === 'queued' || s.state === 'blocked' ? 'text-slate' : '')}>{s.name}</span>
                  <span className="sr-only">{s.state}</span>
                  <span className={cx('chip', s.state === 'done' ? 'chip-good' : s.state === 'running' ? 'chip-water' : 'chip-flat')}>{s.state}</span>
                </li>
              ))}
            </ol>
          </Panel>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Experiments (curves + Oracle cone) */

export function ExperimentsPanel({ run, jobs }: { run?: LiveRun | null; jobs?: JobViewState[] }) {
  if (run !== undefined) return <LiveExperiments run={run} jobs={jobs ?? []} />;
  return <ReplayExperiments />;
}

function LiveExperiments({ run, jobs }: { run: LiveRun | null; jobs: JobViewState[] }) {
  if (!run) {
    return (
      <div>
        <SectionTitle>EXPERIMENTS</SectionTitle>
        <p className="m-1 text-[14px] text-slate">No job has run yet. Battles start when an experiment step submits a real job.</p>
      </div>
    );
  }
  const { job, metricKey, claim, series } = run;
  const all = series.flatMap((s) => s.points);
  const maxStep = Math.max(1, ...all.map((p) => p[0]));
  const vals = [...all.map((p) => p[1]), ...(claim !== null ? [claim] : [])];
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) { lo = 0; hi = 1; }
  if (hi - lo < 1e-9) { hi = lo + 1; }
  const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
  const Wd = 540, Ht = 250, L = 46, R = 10, T = 14, B = 28;
  const x = (st: number) => L + (st / maxStep) * (Wd - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (Ht - T - B);
  const colors = ['#e84040', '#183088'];
  const path = (pts: Array<[number, number]>) => pts.map(([st, v], i) => `${i ? 'L' : 'M'}${x(st).toFixed(1)} ${y(v).toFixed(1)}`).join('');
  const target = series[0]?.points ?? [];
  const last = target[target.length - 1];
  const crossed = claim !== null ? target.find((p) => p[1] >= claim) : undefined;
  const trainPts = series[1]?.points ?? [];
  const sat = trainPts.find((p) => p[1] >= 0.99);
  const cfgOf = (j: JobViewState) => (j.config ? Object.entries(j.config).filter(([k]) => ['model', 'p', 'frac', 'wd', 'lr', 'steps', 'n_estimators', 'device'].includes(k)).map(([k, v]) => `${k}=${String(v)}`).join(' · ') : '—');
  const isSmoke = (j: JobViewState) => j.kit === 'smoke' || (typeof j.config?.steps === 'number' && (j.config.steps as number) <= 200) || (typeof j.config?.n_estimators === 'number' && (j.config.n_estimators as number) <= 10);
  const lastPoint = (j: JobViewState, key: string | undefined) => { const pts = key ? j.metrics[key] : undefined; return pts && pts.length ? pts[pts.length - 1][1] : null; };
  const g = gymForKit(job.kit);
  const finalV = job.final && typeof job.final[metricKey] === 'number' ? (job.final[metricKey] as number) : null;
  const sorted = [...jobs].sort((a, b) => (Number(b.jobId.replace(/\D/g, '')) || 0) - (Number(a.jobId.replace(/\D/g, '')) || 0)).slice(0, 8);
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">{job.jobId} · {job.kit ?? 'job'} · {job.status}</span>}>EXPERIMENTS</SectionTitle>
      <Panel tone="well" className="!m-1 !p-2">
        <svg viewBox={`0 0 ${Wd} ${Ht}`} role="img" aria-label={`${metricKey} over training steps for ${job.jobId}`} className="block h-auto w-full" shapeRendering="crispEdges">
          {[0, 0.25, 0.5, 0.75, 1].map((f) => { const v = lo + f * (hi - lo); return (
            <g key={f}>
              <line x1={L} x2={Wd - R} y1={y(v)} y2={y(v)} stroke="#7878a8" strokeOpacity={0.35} strokeDasharray="4 4" />
              <text x={L - 6} y={y(v) + 3} textAnchor="end" fontFamily="Press Start 2P" fontSize="7" fill="#484878">{v.toFixed(2)}</text>
            </g>); })}
          {claim !== null && (
            <g>
              <line x1={L} x2={Wd - R} y1={y(claim)} y2={y(claim)} stroke="#f8d858" strokeWidth="3" />
              <text x={Wd - R - 4} y={y(claim) - 5} textAnchor="end" fontFamily="Press Start 2P" fontSize="7" fill="#181818">PAPER CLAIM {claim}</text>
            </g>
          )}
          {sat && crossed && crossed[0] > sat[0] && (
            <g>
              <rect x={x(sat[0])} y={T} width={Math.max(2, x(crossed[0]) - x(sat[0]))} height={Ht - T - B} fill="#f85888" fillOpacity="0.14" />
              <text x={(x(sat[0]) + x(crossed[0])) / 2} y={Ht - B - 6} textAnchor="middle" fontFamily="Press Start 2P" fontSize="6" fill="#a02040">MEMORISED, NOT YET GENERALISED</text>
            </g>
          )}
          {series.map((s, i) => <path key={s.key} d={path(s.points)} fill="none" stroke={colors[i % 2]} strokeWidth="3" />)}
          {last && <rect x={x(last[0]) - 4} y={y(last[1]) - 4} width="8" height="8" fill="#f8d858" stroke="#181818" strokeWidth="2" />}
          {crossed && (
            <g>
              <rect x={Math.min(Wd - 120, Math.max(L, x(crossed[0]) - 56))} y={T + 2} width="112" height="18" fill="#f8d858" stroke="#181818" strokeWidth="2" />
              <text x={Math.min(Wd - 64, Math.max(L + 56, x(crossed[0])))} y={T + 15} textAnchor="middle" fontFamily="Press Start 2P" fontSize="7" fill="#181818">CLAIM HIT @ {crossed[0]}</text>
            </g>
          )}
          <text x={L} y={Ht - 8} fontFamily="Press Start 2P" fontSize="7" fill="#484878">STEP → {maxStep}</text>
        </svg>
        <p className="m-0 px-1 pb-1 text-[13px] leading-snug text-ink">
          <b>How to read it:</b> {g ? g.claimText : 'each line is a metric streamed from the running job.'} The yellow line is the paper's claim; the run succeeds when the red line crosses it.
        </p>
        <div className="flex flex-wrap items-center gap-3 px-1 pb-1 text-[13px]">
          {series.map((s, i) => <Legend key={s.key} c={colors[i % 2]} t={`${s.key} (${s.points.length} measured points)`} />)}
          {claim !== null && <Legend c="#f8d858" t={`${g ? `${g.leader}'s` : 'paper'} claim`} />}
        </div>
      </Panel>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead><tr className="font-pixel t-8 text-left text-slate"><th className="p-1">RUN</th><th className="p-1">WHAT</th><th className="p-1">STATUS</th><th className="p-1 text-right">RESULT</th><th className="p-1 text-right">WALL</th><th className="p-1">CHECK</th></tr></thead>
          <tbody>
            {sorted.map((j) => {
              const gg = gymForKit(j.kit);
              const v = gg && j.final && typeof j.final[gg.metricKey] === 'number' ? (j.final[gg.metricKey] as number).toFixed(3) : '—';
              const wall = j.final && typeof j.final.wall_s === 'number' ? `${(j.final.wall_s as number).toFixed(1)} s` : '—';
              return (
                <tr key={j.jobId} className="border-t-2 border-cream-deep align-top">
                  <td className="p-1 font-pixel t-8">{j.jobId}</td>
                  <td className="p-1"><span className={cx('chip', isSmoke(j) ? 'chip-flat' : 'chip-electric')}>{j.kit === 'smoke' ? 'env check' : isSmoke(j) ? 'smoke test' : 'full run'}</span> {j.kit}<span className="block text-[11px] text-slate">{cfgOf(j)}</span></td>
                  <td className="p-1"><span className={cx('chip', j.status === 'ok' ? 'chip-good' : j.status === 'running' ? 'chip-water' : 'chip-bad')}>{j.status === 'stopped' ? '↩ got away' : j.status}</span></td>
                  <td className="p-1 text-right tabular-nums">{gg ? `${gg.metricKey} ${v}` : '—'}</td><td className="p-1 text-right tabular-nums">{wall}</td>
                  <td className="p-1 text-[12px]">{(() => {
                    const lp = gg ? lastPoint(j, gg.metricKey) : null;
                    const fv = gg && j.final && typeof j.final[gg.metricKey] === 'number' ? (j.final[gg.metricKey] as number) : null;
                    const n = gg ? (j.metrics[gg.metricKey]?.length ?? 0) : 0;
                    if (fv !== null && lp !== null) return Math.abs(fv - lp) < 1e-6 ? <span className="text-[#1f8f2a]">✓ final = last streamed point ({n} pts)</span> : <span className="text-[#a02040]">✗ final ≠ stream</span>;
                    return <span className="text-slate">{n} pts</span>;
                  })()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-1 text-[12px] text-slate">LIVE · every point is a job.metric event{finalV !== null ? ` · final ${metricKey} ${finalV.toFixed(3)}` : ''}.</p>
      </div>
    </div>
  );
}

function ReplayExperiments() {
  const { train, test, forecast } = useMemo(() => demoCurves(120), []);
  const [k, setK] = useState(60);
  useEffect(() => {
    const id = window.setInterval(() => setK((p) => (p >= 119 ? 40 : p + 1)), 140);
    return () => window.clearInterval(id);
  }, []);
  const Wd = 540, Ht = 250, L = 38, R = 10, T = 14, B = 28;
  const x = (i: number) => L + (i / 119) * (Wd - L - R);
  const y = (v: number) => T + (1 - v) * (Ht - T - B);
  const path = (arr: number[], to: number) => arr.slice(0, to + 1).map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('');
  const coneTop = forecast.slice(k).map((v, i) => `${i ? 'L' : 'M'}${x(k + i).toFixed(1)} ${y(Math.min(1, v + 0.04 + i * 0.0035)).toFixed(1)}`).join('');
  const coneBot = forecast.slice(k).reverse().map((v, i, a) => `L${x(119 - i).toFixed(1)} ${y(Math.max(0, v - 0.04 - (a.length - 1 - i) * 0.0035)).toFixed(1)}`).join('');
  const grokAt = test.findIndex((v) => v > 0.5);
  const hit = k >= grokAt;
  const runs = [
    { id: '#13', cfg: 'wd 0.1 · frac 0.5', st: 'running', acc: test[k].toFixed(2), s: '14 s' },
    { id: '#12', cfg: 'wd 1.0 · frac 0.3', st: 'ok', acc: '0.97', s: '62 s' },
    { id: '#11', cfg: 'wd 0.0 · frac 0.3', st: 'retreated', acc: '0.11', s: '24 s' },
  ];
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">job #13 · local GPU</span>}>EXPERIMENTS</SectionTitle>
      <Panel tone="well" className="!m-1 !p-2">
        <svg viewBox={`0 0 ${Wd} ${Ht}`} role="img" aria-label="Training and test accuracy curves with the Oracle's forecast band" className="block h-auto w-full" shapeRendering="crispEdges">
          {[0, 0.25, 0.5, 0.75, 1].map((g) => (
            <g key={g}>
              <line x1={L} x2={Wd - R} y1={y(g)} y2={y(g)} stroke="#7878a8" strokeOpacity={0.35} strokeDasharray="4 4" />
              <text x={L - 6} y={y(g) + 3} textAnchor="end" fontFamily="Press Start 2P" fontSize="7" fill="#484878">{g.toFixed(g === 0 || g === 1 ? 0 : 2)}</text>
            </g>
          ))}
          <path d={`${coneTop}${coneBot}Z`} fill="#6890f0" fillOpacity="0.25" />
          <path d={path(forecast, 119)} fill="none" stroke="#6890f0" strokeWidth="2" strokeDasharray="3 4" opacity="0.6" />
          <path d={path(train, k)} fill="none" stroke="#183088" strokeWidth="3" />
          <path d={path(test, k)} fill="none" stroke="#e84040" strokeWidth="3" />
          <rect x={x(k) - 4} y={y(test[k]) - 4} width="8" height="8" fill="#f8d858" stroke="#181818" strokeWidth="2" />
          {hit && (
            <g>
              <rect x={x(grokAt) - 52} y={y(0.5) - 28} width="104" height="18" fill="#f8d858" stroke="#181818" strokeWidth="2" />
              <text x={x(grokAt)} y={y(0.5) - 15} textAnchor="middle" fontFamily="Press Start 2P" fontSize="7" fill="#181818">SUPER EFFECTIVE!</text>
            </g>
          )}
          <text x={L} y={Ht - 8} fontFamily="Press Start 2P" fontSize="7" fill="#484878">STEP →</text>
        </svg>
        <div className="flex flex-wrap items-center gap-3 px-1 pb-1 text-[13px]">
          <Legend c="#183088" t="train acc" /><Legend c="#e84040" t="test acc" /><Legend c="#6890f0" t="Oracle forecast (q10–q90)" />
        </div>
      </Panel>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead><tr className="font-pixel t-8 text-left text-slate"><th className="p-1">RUN</th><th className="p-1">CONFIG</th><th className="p-1">STATUS</th><th className="p-1 text-right">TEST</th><th className="p-1 text-right">WALL</th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="border-t-2 border-cream-deep">
                <td className="p-1 font-pixel t-8">{r.id}</td><td className="p-1">{r.cfg}</td>
                <td className="p-1"><span className={cx('chip', r.st === 'ok' ? 'chip-good' : r.st === 'running' ? 'chip-water' : 'chip-bad')}>{r.st === 'retreated' ? '↩ got away' : r.st}</span></td>
                <td className="p-1 text-right tabular-nums">{r.acc}</td><td className="p-1 text-right tabular-nums">{r.s}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-[12px] text-slate">REPLAY fixture — numbers are illustrative until a real run is streamed from labd.</p>
      </div>
    </div>
  );
}

const Legend = ({ c, t }: { c: string; t: string }) => (
  <span className="inline-flex items-center gap-1"><i className="block h-[6px] w-4" style={{ background: c }} />{t}</span>
);

/* ------------------------------------------------------------------ Safari map (Navigator posterior with fog of war) */

const GW = 30, GH = 18, CELL = 16;
const GOOD: Array<[number, number, number]> = [[0.75, 0.3, 1], [0.55, 0.62, 0.8], [0.2, 0.2, -0.4]];
const mu = (u: number, v: number) => GOOD.reduce((s, [cx0, cy0, a]) => s + a * Math.exp(-(((u - cx0) ** 2 + (v - cy0) ** 2) / 0.05)), 0.25);
const RUNS: Array<[number, number]> = [[0.75, 0.3], [0.2, 0.2], [0.45, 0.45], [0.9, 0.7]];
const sigma = (u: number, v: number) => Math.min(1, Math.min(...RUNS.map(([a, b]) => Math.hypot(u - a, v - b))) * 2.4);

const accColor = (v: number) => `rgb(${Math.round(24 + v * 224)},${Math.round(48 + v * 168)},${Math.round(136 - v * 52)})`;

/** The what-if map: each tile is one REAL grokking run (rows = weight decay, columns = training-data fraction). */
export function ExploreMap({ explore, running, onRun }: { explore: ExploreView | null; running: boolean; onRun: () => void }) {
  const wds = explore?.wds.length ? explore.wds : [0, 0.3, 1];
  const fracs = explore?.fracs.length ? explore.fracs : [0.3, 0.5];
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">LIVE · REAL RUNS</span>}>SAFARI ZONE — THE WHAT-IF MAP</SectionTitle>
      <Panel tone="well" className="!m-1">
        <p className="m-0 text-[14px] leading-snug">
          <b>What is this?</b> A researcher asks <i>"what if weight decay is different?"</i> Oak answers by running the Grokking experiment at several settings. <b>Each tile is one real training run on this GPU.</b> Rows = weight decay, columns = how much of the data the model trains on. Tile colour = the test accuracy it reached; <b>✓ GROKKED</b> means it passed the paper's claim ({explore?.claim ?? 0.95}); fog = not run yet.
        </p>
        <div className="mt-2"><Button small onClick={onRun} disabled={running}>{running ? 'RUNNING…' : explore ? '▶ RUN IT AGAIN' : '▶ RUN THE WHAT-IF'}</Button></div>
      </Panel>
      <div className="m-1 mt-2 overflow-x-auto">
        <table className="w-full border-separate border-spacing-1 text-center">
          <thead>
            <tr><th className="font-pixel t-8 p-1 text-slate">wd ↓ / data →</th>{fracs.map((f) => <th key={f} className="font-pixel t-8 p-1 text-navy">{Math.round(f * 100)}% of data</th>)}</tr>
          </thead>
          <tbody>
            {wds.map((wd) => (
              <tr key={wd}>
                <th className="font-pixel t-8 p-1 text-navy">wd {wd}</th>
                {fracs.map((f) => {
                  const c = explore?.cells.find((x) => x.wd === wd && x.frac === f);
                  const bg = c && c.testAcc !== null ? accColor(Math.max(0, Math.min(1, c.testAcc))) : '#e6e4b0';
                  return (
                    <td key={f} className="p-2 align-middle" style={{ background: bg, boxShadow: c?.claimHitStep != null ? '0 0 0 3px #f8d858 inset' : undefined, minWidth: 120, height: 88 }}>
                      {c ? (
                        <>
                          <p className="m-0 text-[20px] font-bold tabular-nums" style={{ color: c.testAcc !== null && c.testAcc > 0.55 ? '#181818' : '#f8f8d0' }}>{c.testAcc !== null ? c.testAcc.toFixed(2) : '—'}</p>
                          <p className="m-0 text-[12px] font-bold" style={{ color: c.testAcc !== null && c.testAcc > 0.55 ? '#181818' : '#f8f8d0' }}>{c.claimHitStep != null ? `✓ GROKKED @ step ${c.claimHitStep}` : 'NEVER GROKKED'}</p>
                          <p className="m-0 text-[11px] opacity-80" style={{ color: c.testAcc !== null && c.testAcc > 0.55 ? '#181818' : '#f8f8d0' }}>{c.jobId}</p>
                        </>
                      ) : <p className="m-0 text-[13px] text-slate">{explore && running ? 'waiting for its run…' : 'fog (not run)'}</p>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {explore && explore.lines.length > 0 && (
        <>
          <SectionTitle>WHY THE TILES DIFFER (computed from the measured curves)</SectionTitle>
          <ul className="m-1 grid list-none gap-1 p-0 text-[14px] leading-snug">
            {explore.lines.map((l, i) => <li key={i} className="bg-cream-deep p-2">{l}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}

export function SafariPanel({ live = false }: { live?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const g = c?.getContext('2d');
    if (!c || !g) return;
    for (let j = 0; j < GH; j++) {
      for (let i = 0; i < GW; i++) {
        const u = (i + 0.5) / GW, v = (j + 0.5) / GH;
        const m = Math.max(0, Math.min(1, mu(u, v)));
        const r = Math.round(24 + m * 224), gg = Math.round(48 + m * 168), b = Math.round(136 - m * 52);
        g.fillStyle = `rgb(${r},${gg},${b})`;
        g.fillRect(i * CELL, j * CELL, CELL, CELL);
        g.fillStyle = `rgba(230,228,176,${Math.min(0.92, sigma(u, v) * 0.95)})`;
        g.fillRect(i * CELL, j * CELL, CELL, CELL);
        g.fillStyle = 'rgba(24,24,24,0.12)';
        g.fillRect(i * CELL, j * CELL, CELL, 1);
        g.fillRect(i * CELL, j * CELL, 1, CELL);
      }
    }
    RUNS.forEach(([u, v]) => {
      const px = u * GW * CELL, py = v * GH * CELL;
      g.fillStyle = '#181818'; g.fillRect(px - 7, py - 7, 14, 14);
      g.fillStyle = '#e84040'; g.fillRect(px - 5, py - 5, 10, 5);
      g.fillStyle = '#f8f8d0'; g.fillRect(px - 5, py, 10, 5);
      g.fillStyle = '#181818'; g.fillRect(px - 5, py - 1, 10, 2);
    });
  }, []);
  const sx = 0.62 * GW * CELL, sy = 0.78 * GH * CELL;
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">{live ? 'REPLAY FIXTURE' : 'NAVIGATOR · GP POSTERIOR'}</span>}>SAFARI ZONE</SectionTitle>
      {live && <p className="m-1 text-[13px] text-slate">The Navigator is not streaming to the desk yet, so this map is the illustrative fixture, not live data.</p>}
      <Panel tone="well" className="!m-1 !p-2">
        <div className="relative mx-auto w-full max-w-[480px]" style={{ aspectRatio: `${GW} / ${GH}` }}>
          <canvas ref={ref} width={GW * CELL} height={GH * CELL} className="block h-full w-full" style={{ imageRendering: 'pixelated', boxShadow: '0 0 0 3px var(--color-slate)' }} aria-label="Hypothesis map: brighter is better predicted test accuracy; cream fog is unexplored" role="img" />
          <i aria-hidden="true" className="pin-pulse" style={{ borderColor: '#183088', left: `${(sx / (GW * CELL)) * 100}%`, top: `${(sy / (GH * CELL)) * 100}%`, transform: 'translate(-50%,-50%)', marginLeft: 0, width: 34, height: 34 }} />
        </div>
        <div className="mt-2 flex justify-between px-1 font-pixel t-8 text-slate"><span>wd 0</span><span>weight decay →</span><span>wd 1</span></div>
        <p className="m-0 mt-2 text-[14px] leading-snug">The blinking ring is where the Navigator wants to look next — highest expected improvement. Cream fog is unexplored; it lifts as runs finish.</p>
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ Repro report */

export function ReproPanel({ project }: { project?: ProjectViewState | null }) {
  if (project !== undefined) return <LiveRepro project={project} />;
  return <ReplayRepro />;
}

function LiveRepro({ project }: { project: ProjectViewState | null }) {
  if (!project) {
    return (
      <div>
        <SectionTitle>REPRO REPORT</SectionTitle>
        <p className="m-1 text-[14px] text-slate">No project has finished yet. The verdict appears here when Oak publishes project.completed.</p>
      </div>
    );
  }
  const g = gymForKit(project.kit ?? undefined);
  const chip = project.verdict === 'REPRODUCED' ? 'chip-good' : project.verdict === 'PARTIAL' ? 'chip-electric' : 'chip-bad';
  const done = project.plan.filter((s) => s.status === 'done').length;
  return (
    <div>
      <SectionTitle right={<span className={cx('chip', chip)}>{project.verdict ?? '—'}</span>}>REPRO REPORT</SectionTitle>
      <Panel tone="well" className="!m-1">
        <p className="font-pixel t-10 m-0 leading-[1.6] text-navy">{project.title}</p>
        {g && <p className="m-0 text-[14px] text-slate">{g.paper}</p>}
        <div className="mt-2 grid gap-1 text-[15px]">
          <div className="flex justify-between"><span>Paper claim</span><b className="tabular-nums">{project.claim ? `${project.claim.metric} ≥ ${project.claim.value}` : '—'}</b></div>
          <div className="flex justify-between"><span>Our run</span><b className="tabular-nums">{project.value !== null ? `${project.claim?.metric ?? ''} ${project.value.toFixed(3)}` : '—'}</b></div>
          <div className="flex justify-between"><span>Evidence</span><span className="tabular-nums">{project.jobId ?? '—'}</span></div>
          <div className="flex justify-between"><span>Plan</span><span className="tabular-nums">{done}/{project.plan.length} steps done</span></div>
          {g && <div className="flex justify-between"><span>Badge</span><span>{project.badge ? `${g.badge} ✓` : 'not earned'}</span></div>}
        </div>
      </Panel>
      <p className="mt-2 text-[12px] text-slate">LIVE · from project.completed (seq-cited in Activity). The full report is written to var/projects/{project.projectId}/report.md.</p>
    </div>
  );
}

function ReplayRepro() {
  const claims = [
    { c: 'Test acc ≥ 0.95 on mod-97 addition', v: 'REPRODUCED', k: 'chip-good', ev: 'job #12 · 0.97 (seed 0–4 mean 0.96)' },
    { c: 'Generalisation after ~10k steps', v: 'PARTIAL', k: 'chip-electric', ev: 'ours 19.8k ± 3.1k — later than the paper' },
    { c: 'No weight decay → no grokking', v: 'REPRODUCED', k: 'chip-good', ev: 'job #11 retreated at 38 %; Oracle P(success)=0.03' },
  ];
  const hyps = [
    { h: 'H1 seed variance', s: 0.31, e: 'measured ±3.1k over 5 seeds' },
    { h: 'H2 init scale (0.02 vs 1/√d)', s: 0.44, e: '3 diagnostic runs scheduled' },
    { h: 'H3 AdamW β2', s: 0.12, e: 'paper uses 0.98; ours 0.98 — ruled out' },
  ];
  return (
    <div>
      <SectionTitle right={<span className="chip chip-electric">PARTIAL</span>}>REPRO REPORT</SectionTitle>
      <div className="grid gap-2">
        {claims.map((c) => (
          <Panel key={c.c} tone="well" className="!m-1">
            <div className="flex items-start justify-between gap-2"><p className="m-0 text-[15px] font-bold leading-snug">{c.c}</p><span className={cx('chip flex-none', c.k)}>{c.v}</span></div>
            <p className="m-0 text-[13px] text-slate"><b className="font-pixel t-8 text-navy">EVIDENCE </b>{c.ev}</p>
          </Panel>
        ))}
      </div>
      <SectionTitle>WHY DO WE DIFFER?</SectionTitle>
      <div className="grid gap-2">
        {hyps.map((h) => (
          <div key={h.h} className="grid gap-1">
            <div className="flex justify-between text-[14px]"><span className="font-bold">{h.h}</span><span className="text-slate">{h.e}</span></div>
            <div className="bar"><i style={{ width: `${h.s * 100}%`, ['--bar' as string]: '#f85888' }} /></div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[12px] text-slate">REPLAY fixture. In a live run every row links to the run id, seed and config hash that produced it.</p>
    </div>
  );
}



/* ------------------------------------------------------------------ Paper (what the Reader read, what Oak extracted, what the run showed) */

const HILITE = /(grokking|weight decay|test accuracy|generali[sz]ation|train(?:ing)? accuracy|R\^?2|PSNR|distill\w*|teacher|student|soft label\w*)/gi;

/** PDF text extraction leaves artefacts (small-caps splits, hyphenated line breaks, mid-sentence cuts): tidy for reading. */
export function cleanPaperText(raw: string): string {
  let t = raw.replace(/\s+/g, ' ').trim();
  t = t.replace(/\b([A-Z]) ([A-Z]{3,})/g, '$1$2');            // "G ENERALIZATION" -> "GENERALIZATION"
  t = t.replace(/([A-Z]{2,}) ?- ?([A-Z]{2,})/g, '$1$2');       // "OVERFIT - TING" -> "OVERFITTING"
  t = t.replace(/([a-z])- ([a-z])/g, '$1$2');                  // "al- gorithmically" -> "algorithmically"
  if (t.length >= 480) {                                       // cut at the last full sentence, not mid-word
    const end = Math.max(t.lastIndexOf('. '), t.lastIndexOf('? '));
    t = end > 120 ? t.slice(0, end + 1) : t.slice(0, t.lastIndexOf(' ')) + '…';
  }
  return t;
}

function Hilite({ text }: { text: string }) {
  const parts = cleanPaperText(text).split(HILITE);
  return <>{parts.map((t, i) => (i % 2 === 1 ? <mark key={i} className="bg-yellow px-0.5 text-ink">{t}</mark> : <span key={i}>{t}</span>))}</>;
}

export function PaperPanel({ paper, project }: { paper: PaperView | null; project: ProjectViewState | null }) {
  if (!paper) {
    return (
      <div>
        <SectionTitle>PAPER</SectionTitle>
        <p className="m-1 text-[14px] text-slate">Ask Oak to reproduce a paper. When the Reader opens it, its real text chunks, the extracted claims and the analysis of the run appear here, each from a logged event.</p>
      </div>
    );
  }
  const a = paper.analysis;
  return (
    <div>
      <SectionTitle right={<span className="font-pixel t-8 text-slate">{paper.source}</span>}>PAPER</SectionTitle>
      <Panel tone="well" className="!m-1">
        <p className="font-pixel t-10 m-0 leading-[1.6] text-navy">{paper.title}</p>
        <p className="m-0 text-[13px] text-slate">{project?.title ?? ''} · {paper.nChunks} chunks read by the Paper Reader</p>
      </Panel>

      <div className="mt-5" />
      <SectionTitle>1 · WHAT THE READER READ (first {paper.chunks.length} chunks)</SectionTitle>
      <div className="mb-5 grid max-h-72 content-start gap-2 overflow-auto pr-1">
        {paper.chunks.map((c) => (
          <div key={c.id} className="flex-none bg-cream-deep p-2 text-[14px] leading-relaxed"><b className="font-pixel t-8 block text-navy">CHUNK {c.id.split(':').pop()}</b><Hilite text={c.text} /></div>
        ))}
        {paper.chunks.length === 0 && <p className="m-1 text-[13px] text-slate">Waiting for paper.ingested…</p>}
      </div>

      <SectionTitle>2 · WHAT OAK EXTRACTED (the claim to beat)</SectionTitle>
      <div className="mb-5 grid gap-1">
        {paper.claims.map((c, i) => (
          <Panel key={i} tone="well" className="!m-1 !p-2">
            <p className="m-0 text-[14px]"><b>{c.metric} ≥ {c.value}</b>{c.condition ? ` — ${c.condition}` : ''}</p>
            {c.source && <p className="m-0 text-[12px] text-slate">source span: {c.source}</p>}
          </Panel>
        ))}
        {paper.claims.length === 0 && <p className="m-1 text-[13px] text-slate">Waiting for claim.extracted…</p>}
      </div>

      <SectionTitle>3 · WHAT THE RUN SHOWED (analysis of the measured curve)</SectionTitle>
      {a ? (
        <Panel tone="well" className="!m-1">
          <p className="m-0 text-[15px] leading-snug">
            {a.trainSaturatedStep !== null && <>Training accuracy reached 0.99 at step <b>{a.trainSaturatedStep}</b>. </>}
            {a.claimHitStep !== null ? <>{a.metric} reached the paper's <b>{a.claim}</b> at step <b>{a.claimHitStep}</b>{a.delaySteps !== null ? <> — a <b>{a.delaySteps}-step delay</b> between memorising and generalising.</> : '.'}</> : <>{a.metric} never reached the claim ({a.claim}).</>}
          </p>
          <p className="m-0 mt-1 text-[12px] text-slate">Computed from {a.points} job.metric points of {a.jobId}; this delayed jump is what the Grokking paper describes.</p>
        </Panel>
      ) : <p className="m-1 text-[13px] text-slate">Waiting for analysis.computed (the Analyst runs after the full run)…</p>}
    </div>
  );
}
