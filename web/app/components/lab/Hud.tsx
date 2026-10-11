'use client';

import Link from 'next/link';
import { useSyncExternalStore } from 'react';
import { audio } from '@/game/audio';
import { DEMO_HUD } from '@/lib/demo';
import { Icon } from '../Icon';
import { Logotype } from '../Logotype';
import { Button, Panel, StatBar, cx } from '../ui';

export type Layout = 'game' | 'split' | 'console';

function useMuted(): boolean {
  return useSyncExternalStore((cb) => audio.onChange(cb), () => audio.isMuted(), () => false);
}

/**
 * Always-on top bar (§9.7). LIVE vs REPLAY is the first thing a judge sees: it never claims LIVE unless the
 * view is driven by labd events. `approvals` pulses when the researcher is needed.
 */
export function Hud({
  replay,
  labd,
  layout,
  setLayout,
  approvals,
  onApprovals,
  stats,
}: {
  replay: boolean;
  labd: 'connecting' | 'open' | 'closed';
  layout: Layout;
  setLayout: (l: Layout) => void;
  approvals: number;
  onApprovals: () => void;
  /** LIVE numbers (lib/liveView hudStats). Absent = REPLAY fixture values. */
  stats?: { gpu: number | null; vram: string; jobs: number; badges: number; agents: number };
}) {
  const muted = useMuted();
  return (
    <header className="relative z-20 flex items-center gap-x-3 bg-navy px-3 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] text-cream" style={{ boxShadow: '0 4px 0 0 var(--color-gold), 0 8px 0 0 rgba(14,28,92,.5)' }}>
      <Link href="/" className="block w-[104px] flex-none" aria-label="PokéLab home" onClick={() => audio.sfx('menu_back')}>
        <Logotype />
      </Link>

      <span className={cx('chip', replay ? 'chip-electric' : 'chip-good')} title={replay ? 'Driven by a recorded fixture, not by the lab' : 'Driven by live labd events'}>
        <i className={replay ? 'replay-dot' : 'live-dot'} aria-hidden="true" />
        {replay ? 'REPLAY' : 'LIVE'}
      </span>
      <span className="chip chip-plain max-sm:hidden!" title="labd event stream">
        labd · {labd === 'open' ? 'online' : labd === 'connecting' ? 'connecting' : 'offline'}
      </span>

      <div className="hidden min-w-0 flex-1 items-center justify-center gap-4 overflow-hidden lg:flex">
        {stats ? (
          <>
            <div className="hud-bar w-44" title="nvidia-smi via labd /api/telemetry"><StatBar label="GPU" value={stats.gpu ?? 0} max={100} color="#58d858" display={stats.gpu === null ? '—' : `${Math.round(stats.gpu)}%`} /></div>
            <span className="hidden xl:block"><Stat k="VRAM" v={stats.vram} /></span>
            <Stat k="JOBS" v={String(stats.jobs)} hint="jobs running now (job.started without job.done)" />
            <Stat k="TEAM" v={String(stats.agents)} />
            <Stat k="BADGES" v={String(stats.badges)} hint="projects REPRODUCED (project.badge_awarded)" />
          </>
        ) : (
          <>
            <div className="hud-bar w-44"><StatBar label="GPU" value={DEMO_HUD.gpu} max={100} color="#58d858" display={`${DEMO_HUD.gpu}%`} /></div>
            <span className="hidden xl:block"><Stat k="VRAM" v={DEMO_HUD.vram} /></span>
            <Stat k="JOBS" v={String(DEMO_HUD.jobs)} />
            <span className="hidden 2xl:block"><Stat k="TOKENS" v={DEMO_HUD.tokens} /></span>
            <Stat k="SAVED" v={DEMO_HUD.saved} hint="GPU-seconds the Oracle saved by early stops" />
          </>
        )}
      </div>
      <div className="flex-1 lg:hidden" />

      <button
        type="button"
        onClick={onApprovals}
        className={cx('btn btn-sm', approvals ? '' : 'btn-secondary')}
        aria-label={`${approvals} approvals waiting`}
      >
        <span className="font-pixel t-8 max-md:hidden">APPROVALS</span>
        <span className={cx('font-pixel t-8 px-1', approvals ? 'bg-ink text-yellow blink' : '')}>{approvals}</span>
      </button>

      <div className="flex items-center" role="group" aria-label="Layout">
        <span className="contents max-sm:hidden">
        {(['game', 'split', 'console'] as const).map((l, i) => (
          <Button key={l} variant="quiet" small aria-pressed={layout === l} className={layout === l ? '!bg-yellow !text-ink' : ''} onClick={() => { audio.sfx('menu_move'); setLayout(l); }} title={`${l} (${i + 1})`}>
            <span className="font-pixel t-8">{i + 1}<span className="max-xl:hidden">·{l}</span></span>
          </Button>
        ))}
        </span>
        <Button variant="quiet" small icon aria-pressed={muted} aria-label={muted ? 'Turn sound on' : 'Mute sound'} onClick={() => audio.setMuted(!muted)}>
          <Icon name={muted ? 'soundOff' : 'soundOn'} size={18} />
        </Button>
      </div>
    </header>
  );
}

function Stat({ k, v, hint }: { k: string; v: string; hint?: string }) {
  return (
    <p className="m-0 whitespace-nowrap leading-tight" title={hint}>
      <span className="font-pixel t-8 text-cream/70">{k}</span>{' '}
      <span className="font-pixel t-10 tabular-nums text-yellow">{v}</span>
    </p>
  );
}

export { Panel };
