"use client";

import { useEffect, useRef } from "react";
import { BootScene } from "./scenes/BootScene";
import { RegionScene } from "./scenes/RegionScene";
import { LabScene } from "./scenes/LabScene";
import { GymScene } from "./scenes/GymScene";
import { recordFrameTime } from "@/lib/perf";

export function PhaserMount() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let game: import("phaser").Game | undefined;
    let cancelled = false;

    // Phaser touches `window`/WebGL at import time — load it only in the
    // browser, never during Next's static export build.
    import("phaser").then((Phaser) => {
      if (cancelled || !containerRef.current) return;
      game = new Phaser.Game({
        type: Phaser.AUTO,
        width: 640,
        height: 480,
        parent: containerRef.current,
        backgroundColor: "#0b0e14",
        scene: [BootScene, RegionScene, LabScene, GymScene],
        pixelArt: true,
      });
      // P12.3: real per-frame delta straight from Phaser's own step loop,
      // not a separate requestAnimationFrame sampler that could drift
      // from what's actually driving the game.
      game.events.on(Phaser.Core.Events.POST_STEP, (_time: number, delta: number) => {
        recordFrameTime(delta);
      });
    });

    return () => {
      cancelled = true;
      game?.destroy(true);
    };
  }, []);

  return <div ref={containerRef} style={{ width: 640, height: 480, border: "1px solid #2a2f3a" }} />;
}
