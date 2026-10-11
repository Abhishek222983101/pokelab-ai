'use client';

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { audio } from '@/game/audio';
import { Logotype } from './components/Logotype';
import { Panel } from './components/ui';
import { Mon } from './components/Mon';

const PARADE = ['pikachu', 'charmeleon', 'ivysaur', 'wartortle', 'kadabra', 'porygon', 'magneton', 'noctowl', 'golbat', 'eevee'];

/**
 * Title screen. Wordmark on the pixel field, a navy dialog with the menu, the blinking triangle marking
 * the current choice — a handheld's title menu, exactly like its sibling PokeStonks, with a lab's cast.
 */
export default function Title() {
  const router = useRouter();
  const menuRef = useRef<HTMLDivElement>(null);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    void document.fonts?.load('16px "Press Start 2P"').catch(() => {});
    const unlock = () => {
      void audio.unlock().then(() => audio.bgm('title'));
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
    menuRef.current?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true });
    return () => {
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
  }, []);

  const go = useCallback(
    (href: string) => {
      audio.sfx('menu_select');
      setLeaving(true);
      window.setTimeout(() => router.push(href), 520);
    },
    [router],
  );

  const onMenuKey = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') ?? []);
    if (!items.length) return;
    const i = items.indexOf(document.activeElement as HTMLButtonElement);
    items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus();
    audio.sfx('menu_move');
    e.preventDefault();
  }, []);

  return (
    <main className="field fixed inset-0 overflow-hidden">
      <div className={`relative z-10 flex h-full flex-col items-center justify-between px-3 pt-[max(6vh,1.25rem)] pb-[max(0.75rem,env(safe-area-inset-bottom))] ${leaving ? 'boot-out' : ''}`}>
        <header className="w-[min(88vw,36rem)]">
          <h1 className="m-0">
            <Logotype />
          </h1>
          <p className="font-pixel t-10 mt-6 text-center text-navy" style={{ textShadow: '2px 2px 0 rgba(255,255,255,.8)' }}>
            PROFESSOR OAK’S EVOLVING RESEARCH LAB
          </p>
        </header>

        {/* The evolution line: the one idea the product is built on, shown as the thing it is. */}
        <section aria-label="An agent evolving" className="flex flex-col items-center gap-2">
          <div className="flex items-end gap-2 sm:gap-6">
            {(['charmander', 'charmeleon', 'charizard'] as const).map((s, i) => (
              <div key={s} className="flex items-end gap-1 sm:gap-4">
                <div className="bob" style={{ animationDelay: `${i * 220}ms` }}>
                  <Mon species={s} size={i === 2 ? 176 : i === 1 ? 136 : 96} shadow />
                </div>
                {i < 2 && <i aria-hidden="true" className="evo-arrow blink" />}
              </div>
            ))}
          </div>
          <p className="font-pixel t-8 text-navy/80">v1 → v2 → v3 · only when measured better</p>
        </section>

        <Panel tone="dialog" className="w-[min(100%_-_1rem,29rem)]" aria-label="Start menu">
          <p className="text-[17px] leading-snug">
            Watch a team of AI agents read papers, run real experiments on real hardware, and evolve — while you steer.
          </p>
          <div ref={menuRef} role="group" aria-label="Start" onKeyDown={onMenuKey} className="-mx-2 mt-3">
            <button type="button" className="menu-item" onClick={() => go('/lab')}>
              <span>
                Enter the Lab
                <small>Game + console, side by side. Live when labd is running.</small>
              </span>
            </button>
            <button type="button" className="menu-item" onClick={() => go('/lab?mode=replay')}>
              <span>
                Watch the replay
                <small>A recorded session — clearly labelled, always available offline.</small>
              </span>
            </button>
            <button type="button" className="menu-item" onClick={() => go('/m')}>
              <span>
                Open Pokégear
                <small>Approve, redirect and kill from your phone.</small>
              </span>
            </button>
          </div>
        </Panel>
      </div>

      {/* Parade: the roster strolls along the bottom edge. Decorative, so hidden from assistive tech. */}
      <div aria-hidden="true" className="parade pointer-events-none absolute inset-x-0 bottom-0 z-0 h-24 overflow-hidden">
        <div className="parade-track">
          {[...PARADE, ...PARADE].map((s, i) => (
            <Mon key={i} species={s} size={72} />
          ))}
        </div>
      </div>
    </main>
  );
}
