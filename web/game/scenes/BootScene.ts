import Phaser from "phaser";

/** Loads the real manifest built by assets/build_atlases.py (P9.1) and
 * the sprites it points at — nothing here is a placeholder shape. */
export class BootScene extends Phaser.Scene {
  constructor() {
    super("boot");
  }

  preload() {
    // [BUG FOUND via Playwright against a real labd]: a relative path
    // here resolves against the PAGE's URL, not the site root — since
    // this page is served at /game/, "assets/gen/..." 404'd by
    // resolving to /game/assets/gen/... instead of /assets/gen/...
    // Leading slash fixes it regardless of which route mounts the game.
    this.load.json("manifest", "/assets/gen/manifest.json");
  }

  create() {
    const manifest = this.cache.json.get("manifest") as {
      mons: Record<string, { front: string; back: string }>;
      trainers: Record<string, string>;
    };

    this.load.once("complete", () => this.scene.start("region"));
    for (const [species, paths] of Object.entries(manifest.mons)) {
      this.load.image(`mon:${species}:front`, `/${paths.front}`);
      this.load.image(`mon:${species}:back`, `/${paths.back}`);
    }
    for (const [name, path] of Object.entries(manifest.trainers)) {
      this.load.image(`trainer:${name}`, `/${path}`);
    }
    this.load.start();
  }
}
