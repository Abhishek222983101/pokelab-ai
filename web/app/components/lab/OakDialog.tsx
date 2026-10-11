'use client';

import { useEffect, useState } from 'react';
import { trainerPortrait } from '@/lib/roster';
import { Panel } from '../ui';

/**
 * Oak's line, GBA-style: portrait, name, typewriter text, blinking ▼. It shows the text of Oak's latest
 * decision event; when the lab is idle it says nothing new — it never invents lines (§1 rule 1).
 */
export function OakDialog({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { setN(text.length); return; }
    const id = window.setInterval(() => setN((v) => (v >= text.length ? v : v + 1)), 22);
    return () => window.clearInterval(id);
  }, [text]);
  const done = n >= text.length;
  return (
    <Panel tone="dialog" className="!m-1 flex h-[calc(100%-8px)] items-center gap-3 !py-2" aria-live="polite" aria-label="Professor Oak">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={trainerPortrait('oak')} alt="" width={72} height={72} draggable={false} className="flex-none" style={{ imageRendering: 'pixelated', width: 72, height: 72, objectFit: 'contain', background: '#0e1c5c', boxShadow: '0 0 0 3px var(--color-gold)' }} />
      <div className="min-w-0 flex-1">
        <p className="font-pixel t-8 m-0 mb-1 text-yellow">PROF. OAK</p>
        <p className="m-0 text-[17px] leading-snug">
          {text.slice(0, n)}
          {done && <span className="blink ml-1 inline-block text-yellow" aria-hidden="true">▼</span>}
        </p>
      </div>
    </Panel>
  );
}
