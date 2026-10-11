'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import { audio } from '@/game/audio';
import type { SceneAgent } from '@/game/labroom/LabScene';
import { ROLES, EEVEE_FORMS } from '@/lib/roster';
import { useLabConnection } from '@/lib/useLabConnection';
import { useLabStore } from '@/lib/store';
import { useReplay } from '@/lib/useReplay';
import { hudStats, latestCompleted, liveAgents, liveFeed, liveQuests, liveRun, oakLine, type Telemetry } from '@/lib/liveView';
import { labApiUrl } from '@/lib/useLabConnection';
import { Hud, type Layout } from '../components/lab/Hud';
import { ActivityPanel, ExperimentsPanel, Inspector, QuestsPanel, ReproPanel, SafariPanel, TeamPanel, labelOf } from '../components/lab/panels';
import { Mon } from '../components/Mon';
import { OakDialog } from '../components/lab/OakDialog';
import { cx } from '../components/ui';

// Phaser needs the DOM/WebGL — never server-rendered.
const LabMount = dynamic(() => import('@/game/labroom/LabMount'), { ssr: false });

type Tab = 'quests' | 'team' | 'activity' | 'experiments' | 'safari' | 'repro';
const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'team', label: 'TEAM' },
  { id: 'quests', label: 'QUESTS' },
  { id: 'activity', label: 'ACTIVITY' },
  { id: 'experiments', label: 'EXPERIMENTS' },
  { id: 'safari', label: 'SAFARI' },
  { id: 'repro', label: 'REPRO' },
];

const SPECIES = Array.from(new Set([...ROLES.flatMap((r) => r.line), ...EEVEE_FORMS, 'eevee']));

function Desk() {
  const params = useSearchParams();
  const labd = useLabStore((s) => s.connectionStatus);
  const socket = useLabConnection();
  const view = useLabStore((s) => s);
  // Honesty rule (§1): LIVE exactly when labd's event stream is connected — every panel then renders the
  // event fold (lib/liveView). Only while labd is unreachable does the clearly-labelled REPLAY fixture run.
  const live = labd === 'open';
  const replay = !live;
  const rp = useReplay(replay);
  const agents = useMemo(() => (live ? liveAgents(view) : rp.agents), [live, view, rp.agents]);
  const feed = useMemo(() => (live ? liveFeed(view) : rp.feed), [live, view, rp.feed]);
  const quests = useMemo(() => (live ? liveQuests(view) : undefined), [live, view]);
  const run = useMemo(() => (live ? liveRun(view) : undefined), [live, view]);
  const done = useMemo(() => (live ? latestCompleted(view) : undefined), [live, view]);
  const oakSay = live ? oakLine(view) : rp.oakSay;
  const { approved, approveSpawn, rejectSpawn } = rp;

  const [tel, setTel] = useState<Telemetry | null>(null);
  useEffect(() => {
    if (!live) return;
    let stop = false;
    const poll = async () => {
      try { const r = await fetch(labApiUrl('/api/telemetry')); if (r.ok && !stop) setTel(await r.json()); } catch { /* labd restarting */ }
    };
    void poll();
    const id = window.setInterval(poll, 2000);
    return () => { stop = true; window.clearInterval(id); };
  }, [live]);
  const stats = live ? hudStats(view, tel) : undefined;

  const [ask, setAsk] = useState('');
  const [askNote, setAskNote] = useState('');
  useEffect(() => socket.onCommandResult((r) => {
    if (r.command === 'request') setAskNote(r.ok ? 'Sent — Oak is on it (watch ACTIVITY).' : `Refused: ${r.detail}`);
    if (r.command === 'feedback') setAskNote(r.ok ? 'Feedback recorded as a human.feedback event.' : `Refused: ${r.detail}`);
  }), [socket]);
  const sendAsk = (text: string) => {
    if (!text.trim()) return;
    audio.sfx('menu_select');
    if (socket.sendRequest(text.trim())) { setAsk(''); setAskNote('Sending…'); setTab('activity'); } else setAskNote('labd is not connected — nothing was sent.');
  };
  const feedback = (agentId: string, value: number) => {
    if (!socket.sendCommand('feedback', undefined, { agent_id: agentId, value })) setAskNote('labd is not connected — nothing was sent.');
  };

  const [layout, setLayout] = useState<Layout>('split');
  const [tab, setTab] = useState<Tab>('team');
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    void document.fonts?.load('16px "Press Start 2P"').catch(() => {});
    const unlock = () => {
      void audio.unlock().then(() => audio.bgm('overworld'));
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
    return () => {
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement | null)?.closest('input,textarea')) return;
      if (e.key === '1') setLayout('game');
      if (e.key === '2') setLayout('split');
      if (e.key === '3') setLayout('console');
      if (e.key === 'Escape') setSelected(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => { if (params.get('mode') === 'replay') setLayout('split'); }, [params]);

  const sceneAgents = useMemo<SceneAgent[]>(
    () => agents.map((a) => ({ id: a.id, species: a.name, label: labelOf(a), status: a.status, station: a.station, thought: a.thought })),
    [agents],
  );

  const select = useCallback((id: string) => { audio.sfx('menu_select'); setSelected(id); setTab('team'); setLayout((l) => (l === 'game' ? 'split' : l)); }, []);
  const focusWho = useCallback((who: string) => { const a = agents.find((x) => x.name === who); if (a) select(a.id); }, [agents, select]);

  const sel = agents.find((a) => a.id === selected) ?? null;
  const approvals = !approved && agents.some((a) => a.id === 'a-eevee') ? 1 : 0;
  const showGame = layout !== 'console';
  const showConsole = layout !== 'game';

  return (
    <main className="fixed inset-0 flex flex-col bg-navy-deep">
      <Hud replay={replay} labd={labd} stats={stats} layout={layout} setLayout={setLayout} approvals={approvals} onApprovals={() => { setTab('team'); const e = agents.find((a) => a.id === 'a-eevee'); if (e) setSelected(e.id); }} />
      <div className="relative flex min-h-0 flex-1 flex-col lg:flex-row">
        {showGame && (
          <section aria-label="Oak's Lab" className={cx('relative flex min-h-0 flex-col items-center justify-center', layout === 'split' ? 'basis-3/5 max-lg:basis-1/2' : 'flex-1')} style={{ minWidth: 0 }}>
            <div className="relative w-full" style={{ aspectRatio: '3 / 2', maxHeight: 'calc(100% - 128px)' }}>
              <LabMount agents={sceneAgents} species={SPECIES} selected={selected} oakSay="" onSelect={select} />
              <div className="pointer-events-none absolute left-2 top-2 flex items-center gap-2">
                <span className="chip chip-plain">Shift+E · event ids</span>
              </div>
            </div>
            <div className="w-full flex-none px-2 pb-1" style={{ height: 120 }}>
              <OakDialog text={oakSay} />
            </div>
          </section>
        )}
        {showConsole && (
          <aside aria-label="Console" className={cx('relative flex min-h-0 flex-col', layout === 'split' ? 'basis-2/5 max-lg:basis-1/2' : 'flex-1')}>
            <div className="m-2 mb-0 flex min-h-0 flex-1 flex-col">
              <div className="panel panel-dialog !m-1 flex min-h-0 flex-1 flex-col !p-0">
                <div role="tablist" aria-label="Console panels" className="flex flex-none overflow-x-auto bg-navy-deep px-1 scroll-px">
                  {TABS.map((t) => (
                    <button key={t.id} role="tab" aria-selected={tab === t.id} className="tab" onClick={() => { audio.sfx('menu_move'); setTab(t.id); }}>
                      {t.label}
                      {t.id === 'activity' && <span className="count">{feed.length}</span>}
                    </button>
                  ))}
                </div>
                <div className="scroll-px min-h-0 flex-1 overflow-y-auto bg-cream p-3 text-ink" role="tabpanel">
                  {sel && tab === 'team' && (
                    <div className="mb-3"><Inspector agent={sel} approved={approved} onClose={() => setSelected(null)} onApprove={() => { audio.sfx('levelup'); approveSpawn(); }} onReject={rejectSpawn} onFeedback={live ? (v) => feedback(sel.id, v) : undefined} /></div>
                  )}
                  {tab === 'team' && <TeamPanel agents={agents} selected={selected} onSelect={select} />}
                  {tab === 'quests' && <QuestsPanel quests={quests} />}
                  {tab === 'activity' && <ActivityPanel feed={feed} onFocus={focusWho} />}
                  {tab === 'experiments' && <ExperimentsPanel run={run} jobs={live ? Object.values(view.jobs) : undefined} />}
                  {tab === 'safari' && <SafariPanel live={live} />}
                  {tab === 'repro' && <ReproPanel project={done} />}
                </div>
              </div>
            </div>
            {live ? (
              <form className="m-2 mt-1 flex flex-none flex-col gap-1" onSubmit={(e) => { e.preventDefault(); sendAsk(ask); }}>
                <div className="flex gap-2">
                  <label htmlFor="ask-oak" className="sr-only">Ask Prof. Oak</label>
                  <input id="ask-oak" value={ask} onChange={(e) => setAsk(e.target.value)} placeholder="Ask Oak: reproduce grokking…" className="min-w-0 flex-1 bg-cream px-2 py-1 text-[15px] text-ink" style={{ boxShadow: '0 0 0 3px var(--color-gold)' }} />
                  <button type="submit" className="btn btn-sm">ASK OAK</button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {['Reproduce grokking', 'Reproduce knowledge distillation', 'Reproduce tiny NeRF', 'Reproduce the materials benchmark', 'Reproduce the tabular arena'].map((q) => (
                    <button key={q} type="button" className="chip chip-plain cursor-pointer" onClick={() => sendAsk(q)}>{q}</button>
                  ))}
                </div>
                {askNote && <p className="m-0 text-[12px] text-cream/80" role="status">{askNote}</p>}
              </form>
            ) : (
              <p className="m-0 flex items-center gap-2 px-3 py-1 text-[12px] text-cream/70"><Mon species="porygon" size={16} />Replay fixture · labd {labd === 'connecting' ? 'connecting…' : 'offline'} · start <code>just up</code> for live data</p>
            )}
          </aside>
        )}
      </div>
    </main>
  );
}

export default function LabPage() {
  return (
    <Suspense fallback={null}>
      <Desk />
    </Suspense>
  );
}
