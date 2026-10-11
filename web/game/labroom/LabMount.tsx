'use client';

import { useEffect, useRef } from 'react';
import type Phaser from 'phaser';
import type { SceneAgent } from './LabScene';
import { SCENE_REG } from './LabScene';

interface Props {
  agents: SceneAgent[];
  species: string[];
  selected: string | null;
  oakSay: string;
  onSelect: (id: string) => void;
}

/**
 * Hosts the Lab scene. The Phaser game lives in a ref (never state) and is destroyed on unmount, which makes
 * React 19 StrictMode's mount → unmount → remount safe. Props flow in through the Phaser registry: the scene
 * is a pure function of them.
 */
export default function LabMount({ agents, species, selected, oakSay, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const latest = useRef({ agents, selected, oakSay, onSelect });
  latest.current = { agents, selected, oakSay, onSelect };
  const speciesKey = species.join(',');

  useEffect(() => {
    if (!host.current) return;
    let cancelled = false;
    (async () => {
      await Promise.all([
        document.fonts?.load('8px "Press Start 2P"'),
        document.fonts?.load('bold 13px "Atkinson Hyperlegible Next"'),
      ]).catch(() => {});
      const [{ default: PhaserLib }, { LabScene }] = await Promise.all([import('phaser'), import('./LabScene')]);
      if (cancelled || !host.current) return;
      const game = new PhaserLib.Game({
        type: PhaserLib.AUTO,
        parent: host.current,
        width: 960,
        height: 640,
        backgroundColor: '#0e1c5c',
        pixelArt: true,
        roundPixels: true,
        antialias: false,
        disableContextMenu: true,
        scale: { mode: PhaserLib.Scale.FIT, autoCenter: PhaserLib.Scale.CENTER_BOTH },
        scene: [LabScene],
        callbacks: {
          preBoot: (g) => {
            g.registry.set(SCENE_REG.species, speciesKey.split(',').filter(Boolean));
            g.registry.set(SCENE_REG.agents, latest.current.agents);
            g.registry.set(SCENE_REG.selected, latest.current.selected);
            g.registry.set(SCENE_REG.oakSay, latest.current.oakSay);
            g.registry.set(SCENE_REG.onSelect, (id: string) => latest.current.onSelect(id));
          },
        },
      });
      gameRef.current = game;
      if (process.env.NODE_ENV !== 'production') (window as unknown as { __lab?: unknown }).__lab = game;
    })();
    return () => {
      cancelled = true;
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, [speciesKey]);

  useEffect(() => { gameRef.current?.registry.set(SCENE_REG.agents, agents); }, [agents]);
  useEffect(() => { gameRef.current?.registry.set(SCENE_REG.selected, selected); }, [selected]);
  useEffect(() => { gameRef.current?.registry.set(SCENE_REG.oakSay, oakSay); }, [oakSay]);

  return <div ref={host} className="absolute inset-0" style={{ touchAction: 'none', background: '#0e1c5c' }} />;
}
