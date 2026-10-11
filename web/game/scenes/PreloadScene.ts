import * as Phaser from 'phaser';
import { artSteps, type ArtStep } from '../art/register';
import { C, FONT, H, W, drawFrame, notched } from '../overworld/ui';
import { buildCampus, buildLab, MAP } from '../overworld/campus';
import { buildTownMap, buildInterior, TOWNS, INTERIORS } from '../overworld/towns';
import {
  MANIFEST_KEY, MANIFEST_URL, addPeopleAliases, createAgentAnims, queueOverworldAssets, walkKey, type Manifest,
} from '../lab/assets';
import type { LabWorldMap } from '../overworld/campus';

const MIN_SPLASH_MS = 700;
const ROLL_CALL = ['pikachu', 'charmander', 'bulbasaur', 'squirtle', 'abra', 'porygon', 'magnemite', 'hoothoot', 'zubat', 'eevee'];

/**
 * PokéLab splash (PokeStonks PreloadScene, extended per §9.3): the progress bar tracks real work —
 * every procedural texture group, the real sprite atlases from assets/build_atlases.py, and every
 * map build — and the team's actual Pokémon walk onto the screen as their atlases arrive.
 */
export class PreloadScene extends Phaser.Scene {
  constructor() {
    super('Preload');
  }

  preload() {
    this.load.json(MANIFEST_KEY, MANIFEST_URL);
  }

  create() {
    const started = this.time.now;
    const cam = this.cameras.main;
    cam.setBackgroundColor('#0f1f5c');
    cam.fadeIn(180, 15, 31, 92);

    const bg = this.add.graphics();
    bg.fillStyle(0x142a78, 1);
    for (let i = -6; i < 16; i++) {
      bg.beginPath();
      bg.moveTo(i * 90, 0); bg.lineTo(i * 90 + 44, 0); bg.lineTo(i * 90 + 44 - 260, H); bg.lineTo(i * 90 - 260, H);
      bg.closePath(); bg.fillPath();
    }

    const title = this.add.text(W / 2, 190, 'POKéLAB', {
      fontFamily: FONT, fontSize: '72px', color: '#f8d858', stroke: '#181818', strokeThickness: 12,
    }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2 + 4, 194, 'POKéLAB', { fontFamily: FONT, fontSize: '72px', color: '#a8781c' }).setOrigin(0.5).setResolution(2).setDepth(-1);
    this.add.text(W / 2, 258, "PROF. OAK'S EVOLVING RESEARCH LAB", { fontFamily: FONT, fontSize: '14px', color: '#f8f8d0' }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 284, 'EVERY BATTLE IS A REAL TRAINING RUN', { fontFamily: FONT, fontSize: '10px', color: '#a8b8f8' }).setOrigin(0.5).setResolution(2);
    this.tweens.add({ targets: title, y: 184, duration: 900, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });

    const bx = W / 2 - 280, by = 360, bw = 560, bh = 34;
    const frame = this.add.graphics();
    drawFrame(frame, bx - 8, by - 8, bw + 16, bh + 16, { fill: C.navyDark, border: C.gold, borderW: 5, inner: C.white });
    const fill = this.add.graphics();
    const label = this.add.text(W / 2, by + bh + 34, 'WAKING THE LAB...', { fontFamily: FONT, fontSize: '11px', color: '#c8c8f0' }).setOrigin(0.5).setResolution(2);
    const setProgress = (p: number, text: string) => {
      fill.clear();
      const w = Math.round((bw - 8) * Math.max(0, Math.min(1, p)));
      if (w > 0) {
        notched(fill, bx + 4, by + 4, w, bh - 8, 0x58d858, 1, 2);
        fill.fillStyle(0xa8f8a8, 1);
        fill.fillRect(bx + 6, by + 6, Math.max(0, w - 4), 4);
      }
      label.setText(text.toUpperCase());
    };

    const manifest = this.cache.json.get(MANIFEST_KEY) as Manifest | undefined;
    if (!manifest) {
      setProgress(0, 'Sprites missing: run `just atlases`');
      return;
    }
    this.registry.set('manifest', manifest);

    // the team walks in as their walk atlases finish loading
    const shown = new Set<string>();
    const rollCall = () => {
      ROLL_CALL.forEach((sp, i) => {
        if (shown.has(sp) || !this.textures.exists(walkKey(sp)) || !this.anims.exists(`${sp}:walk_down`)) return;
        shown.add(sp);
        const x = W / 2 - (ROLL_CALL.length - 1) * 36 + i * 72;
        const s = this.add.sprite(x, 560, walkKey(sp)).setScale(0).play(`${sp}:walk_down`);
        this.tweens.add({ targets: s, scale: 2, duration: 260, ease: 'Back.easeOut' });
      });
    };

    const steps: ArtStep[] = [
      // procedural tiles, characters, battle arenas — minus PokeStonks' BrokerMon (we use real Pokémon)
      ...artSteps(this).slice(1).filter((s) => !s.label.startsWith('BrokerMon')),
      { label: 'Surveying Pallet Campus', run: () => this.registerMap(MAP.campus, buildCampus('bluechip')) },
      { label: "Opening Prof. Oak's Lab", run: () => this.registerMap(MAP.lab, buildLab('bluechip')) },
      ...TOWNS.map((t) => ({ label: `Building ${t.title}`, run: () => this.registerMap(t.key, buildTownMap(t)) })),
      ...INTERIORS.map((i) => ({ label: `Furnishing ${i.title}`, run: () => this.registerMap(i.key, buildInterior(i)) })),
    ];
    const ART_SHARE = 0.55;

    let i = 0;
    const next = () => {
      if (!this.sys.isActive()) return;
      if (i >= steps.length) { loadSprites(); return; }
      const s = steps[i++];
      s.run();
      setProgress((i / steps.length) * ART_SHARE, s.label);
      this.time.delayedCall(0, next);
    };

    const loadSprites = () => {
      queueOverworldAssets(this, manifest);
      this.load.on('progress', (p: number) => setProgress(ART_SHARE + p * (1 - ART_SHARE), 'Calling the team'));
      this.load.on('filecomplete', () => { addPeopleAliases(this, manifest); createAgentAnims(this, manifest); rollCall(); });
      this.load.once('complete', () => {
        addPeopleAliases(this, manifest);
        createAgentAnims(this, manifest);
        rollCall();
        setProgress(1, 'Ready!');
        const wait = Math.max(0, MIN_SPLASH_MS - (this.time.now - started));
        this.time.delayedCall(wait + 300, () => {
          let left = false;
          const leave = () => { if (left || !this.sys.isActive()) return; left = true; this.scene.start('Region'); };
          cam.fadeOut(180, 0, 0, 0);
          cam.once('camerafadeoutcomplete', leave);
          this.time.delayedCall(420, leave);
        });
      });
      this.load.start();
    };
    this.time.delayedCall(40, next);
  }

  private registerMap(key: string, built: LabWorldMap) {
    this.registry.set(`map:${key}`, built);
    if (!this.cache.tilemap.exists(built.key)) this.cache.tilemap.add(built.key, { format: Phaser.Tilemaps.Formats.TILED_JSON, data: built.json });
  }
}
