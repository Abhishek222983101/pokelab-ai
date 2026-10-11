import * as Phaser from 'phaser';
import type { AgentStatus, Station } from '@/lib/demo';
import { ASH_HOME, H, OAK_HOME, STATIONS, W, standPoint } from './layout';
import { PAL, drawFloor, drawFurniture, drawLight, drawWall, drawWindows } from './draw';

/** What the scene needs to know about one agent. The scene is a pure function of this list (binding rule §1). */
export interface SceneAgent {
  id: string;
  species: string;
  label: string; // "Charmeleon v2 · Lv 63"
  status: AgentStatus;
  station: Station;
  thought: string;
}

export const SCENE_REG = { agents: 'agents', species: 'species', onSelect: 'onSelect', selected: 'selected', oakSay: 'oakSay', overlay: 'overlay' } as const;

const DIRS = ['down', 'right', 'up', 'left'] as const;
type Dir = (typeof DIRS)[number];
const FONT_PX = '"Press Start 2P"';
const FONT_BODY = '"Atkinson Hyperlegible Next", system-ui, sans-serif';
const STATUS_COLOR: Record<AgentStatus, number> = { idle: 0x7878a8, asleep: 0x484878, working: 0x6890f0, thinking: 0xf8d030, error: 0xe84040 };
const SPEED = 150; // px/s
const SCALE = 2;

interface Ent {
  id: string;
  species: string;
  station: Station;
  status: AgentStatus;
  root: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Sprite;
  ring: Phaser.GameObjects.Graphics;
  sel: Phaser.GameObjects.Graphics;
  plate: Phaser.GameObjects.Text;
  bubble: Phaser.GameObjects.Container | null;
  bubbleText: string;
  thought: string;
  bubbleTimer?: Phaser.Time.TimerEvent;
  alert: Phaser.GameObjects.Text;
  facing: Dir;
  walking: boolean;
  tween?: Phaser.Tweens.Tween;
  seqTag: Phaser.GameObjects.Text;
}

interface AnimDef { frames: string[]; durations: number[] }

export class LabScene extends Phaser.Scene {
  private ents = new Map<string, Ent>();
  private leds: Array<{ g: Phaser.GameObjects.Rectangle; phase: number }> = [];
  private oak!: Phaser.GameObjects.Sprite;
  private ash!: Phaser.GameObjects.Sprite;
  private oakBubble: Phaser.GameObjects.Container | null = null;
  private oakText = '';
  private ready = false;

  constructor() {
    super('Lab');
  }

  preload() {
    const cam = this.cameras.main;
    cam.setBackgroundColor('#0e1c5c');
    const bw = 420, bx = (W - bw) / 2, by = H / 2;
    const frame = this.add.graphics();
    frame.fillStyle(PAL.gold, 1).fillRect(bx - 10, by - 10, bw + 20, 44);
    frame.fillStyle(PAL.navy, 1).fillRect(bx - 6, by - 6, bw + 12, 36);
    const fill = this.add.graphics();
    this.add.text(W / 2, by - 44, 'WAKING THE LAB...', { fontFamily: FONT_PX, fontSize: '14px', color: '#f8d858' }).setOrigin(0.5).setResolution(2);
    this.load.on('progress', (p: number) => {
      fill.clear().fillStyle(PAL.green, 1).fillRect(bx, by, Math.round(bw * p), 24).fillStyle(0xa8f8a8, 1).fillRect(bx, by, Math.round(bw * p), 6);
    });

    const species = (this.registry.get(SCENE_REG.species) as string[]) ?? [];
    for (const sp of species) {
      this.load.atlas(`w:${sp}`, `/assets/gen/walk/${sp}.png`, `/assets/gen/walk/${sp}.json`);
      this.load.json(`wj:${sp}`, `/assets/gen/walk/${sp}.json`);
    }
    for (const p of ['oak', 'red']) this.load.atlas(`p:${p}`, `/assets/gen/people/${p}.png`, `/assets/gen/people/${p}.json`);
  }

  create() {
    this.children.removeAll(true); // drop the loading bar
    this.cameras.main.setBackgroundColor('#0e1c5c');
    const floor = this.add.graphics().setDepth(0);
    drawFloor(floor);
    const wall = this.add.graphics().setDepth(0.1);
    drawWall(wall);
    drawWindows(wall);
    const leds = drawFurniture(this);
    this.leds = leds.map((l, i) => ({ g: this.add.rectangle(l.x, l.y, 6, 6, l.color).setDepth(0.4), phase: i * 137 }));
    drawLight(this);

    this.buildAnims();
    this.buildPeople();

    this.registry.events.on('changedata', this.onData, this);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.registry.events.off('changedata', this.onData, this));

    this.input.keyboard?.on('keydown-E', (e: KeyboardEvent) => {
      if (e.shiftKey) this.registry.set(SCENE_REG.overlay, !this.registry.get(SCENE_REG.overlay));
    });

    this.ready = true;
    this.reconcile();
    this.refreshSelection();
    this.refreshOak();
  }

  update(time: number) {
    for (const l of this.leds) l.g.setAlpha(0.35 + 0.65 * (0.5 + 0.5 * Math.sin((time + l.phase) / 260)));
    // depth sort by feet so walkers pass in front of / behind each other
    this.ents.forEach((e) => {
      e.root.setDepth(10 + e.root.y / 10);
      if (e.bubble) {
        const w = e.bubble.getData('w') as number, h = e.bubble.getData('h') as number;
        e.bubble.setPosition(Phaser.Math.Clamp(e.root.x, w / 2 + 8, W - w / 2 - 8), Math.max(h + 12, e.root.y - 76));
      }
    });
    this.oak?.setDepth(10 + this.oak.y / 10);
    this.ash?.setDepth(10 + this.ash.y / 10);
  }

  /* ------------------------------------------------------------------ data in */

  private onData(_p: unknown, key: string) {
    if (!this.ready) return;
    if (key === SCENE_REG.agents) this.reconcile();
    else if (key === SCENE_REG.selected) this.refreshSelection();
    else if (key === SCENE_REG.oakSay) this.refreshOak();
    else if (key === SCENE_REG.overlay) this.ents.forEach((e) => e.seqTag.setVisible(!!this.registry.get(SCENE_REG.overlay)));
  }

  private buildAnims() {
    const species = (this.registry.get(SCENE_REG.species) as string[]) ?? [];
    for (const sp of species) {
      const json = this.cache.json.get(`wj:${sp}`) as { anims?: Record<string, AnimDef> } | undefined;
      if (!json?.anims) continue;
      for (const [name, def] of Object.entries(json.anims)) {
        const key = `${sp}:${name}`;
        if (this.anims.exists(key)) continue;
        this.anims.create({
          key,
          frames: def.frames.map((f, i) => ({ key: `w:${sp}`, frame: f, duration: Math.max(0, (def.durations[i] ?? 100) - 1) })),
          frameRate: 1000,
          repeat: -1,
        });
      }
    }
    // FireRed people: 2-frame walk cycles per direction
    for (const p of ['oak', 'red']) {
      for (const d of DIRS) {
        this.anims.create({
          key: `p:${p}:walk_${d}`,
          frames: [`${d}_walk1`, `${d}_idle`, `${d}_walk2`, `${d}_idle`].map((f) => ({ key: `p:${p}`, frame: f })),
          frameRate: 7,
          repeat: -1,
        });
      }
    }
  }

  private buildPeople() {
    this.oak = this.add.sprite(OAK_HOME.x, OAK_HOME.y, 'p:oak', 'down_idle').setOrigin(0.5, 1).setScale(3);
    this.ash = this.add.sprite(ASH_HOME.x, ASH_HOME.y, 'p:red', 'right_idle').setOrigin(0.5, 1).setScale(3);
    this.tweens.add({ targets: this.oak, y: OAK_HOME.y - 2, duration: 900, yoyo: true, repeat: -1, ease: 'Stepped' });
    [this.oak, this.ash].forEach((s) => {
      this.add.ellipse(s.x, s.y - 2, 40, 12, 0x181818, 0.25).setDepth(5);
    });
  }

  /* ------------------------------------------------------------------ agents */

  private reconcile() {
    const agents = (this.registry.get(SCENE_REG.agents) as SceneAgent[]) ?? [];
    // stable slot per station
    const slots = new Map<Station, number>();
    const seen = new Set<string>();
    for (const a of agents) {
      if (!this.textures.exists(`w:${a.species}`)) continue; // species without a walker atlas: skip rather than crash
      seen.add(a.id);
      const slot = slots.get(a.station) ?? 0;
      slots.set(a.station, slot + 1);
      let e = this.ents.get(a.id);
      if (!e) e = this.spawn(a, slot);
      this.apply(e, a, slot);
    }
    this.ents.forEach((e, id) => {
      if (!seen.has(id)) {
        e.bubble?.destroy();
        e.root.destroy();
        this.ents.delete(id);
      }
    });
  }

  private spawn(a: SceneAgent, slot: number): Ent {
    const p = standPoint(a.station, slot);
    const root = this.add.container(p.x, p.y);
    const shadow = this.add.ellipse(0, -2, 44, 14, 0x181818, 0.28);
    const sel = this.add.graphics();
    const ring = this.add.graphics();
    const sprite = this.add.sprite(0, 0, `w:${a.species}`, undefined).setOrigin(0.5, 0.78).setScale(SCALE);
    const plate = this.add.text(0, 12, a.label, { fontFamily: FONT_PX, fontSize: '8px', color: '#f8f8d0', backgroundColor: '#183088', padding: { x: 5, y: 4 } })
      .setOrigin(0.5, 0).setResolution(2);
    const seqTag = this.add.text(0, -92, '', { fontFamily: FONT_PX, fontSize: '7px', color: '#181818', backgroundColor: '#f8d858', padding: { x: 3, y: 2 } }).setOrigin(0.5).setVisible(false).setResolution(2);
    const alert = this.add.text(0, -80, '!', { fontFamily: FONT_PX, fontSize: '16px', color: '#181818', backgroundColor: '#f8d858', padding: { x: 6, y: 5 } }).setOrigin(0.5).setVisible(false).setResolution(2);
    this.tweens.add({ targets: alert, y: -88, duration: 380, yoyo: true, repeat: -1, ease: 'Stepped' });
    root.add([shadow, sel, sprite, ring, plate, seqTag, alert]);
    root.setSize(64, 72);
    sprite.setInteractive({ useHandCursor: true });
    sprite.on('pointerdown', () => (this.registry.get(SCENE_REG.onSelect) as ((id: string) => void) | undefined)?.(a.id));
    sprite.on('pointerover', () => sprite.setTint(0xffffff).setScale(SCALE * 1.06));
    sprite.on('pointerout', () => sprite.setScale(SCALE));

    const e: Ent = { id: a.id, species: a.species, station: a.station, status: a.status, root, sprite, ring, sel, plate, bubble: null, bubbleText: '', thought: a.status === 'working' || a.status === 'thinking' ? a.thought : '', alert, facing: 'down', walking: false, seqTag };
    this.ents.set(a.id, e);
    this.play(e, 'idle');
    // poof-in
    root.setAlpha(0).setScale(0.6);
    this.tweens.add({ targets: root, alpha: 1, scale: 1, duration: 260, ease: 'Back.easeOut' });
    return e;
  }

  private play(e: Ent, kind: 'walk' | 'idle' | 'sleep') {
    const key = `${e.species}:${kind}_${e.facing}`;
    if (this.anims.exists(key)) e.sprite.play(key, true);
  }

  private apply(e: Ent, a: SceneAgent, slot: number) {
    // evolution: species swap with the classic white flash
    if (e.species !== a.species && this.textures.exists(`w:${a.species}`)) {
      e.species = a.species;
      e.sprite.setTexture(`w:${a.species}`);
      e.sprite.setTintFill(0xffffff);
      this.tweens.add({ targets: e.sprite, scale: SCALE * 1.5, duration: 160, yoyo: true, repeat: 2, onComplete: () => { e.sprite.clearTint(); e.sprite.setScale(SCALE); } });
    }
    e.plate.setText(a.label);
    e.status = a.status;
    e.plate.setVisible(a.status !== 'asleep' || this.registry.get(SCENE_REG.selected) === a.id);
    this.drawRing(e);
    e.alert.setVisible(a.station === 'door');
    // Bubbles are transient: a changed thought speaks for a few seconds; the selected agent always speaks.
    const thought = a.status === 'working' || a.status === 'thinking' ? a.thought : '';
    const changed = thought !== e.thought;
    e.thought = thought;
    if (changed && thought) {
      this.setBubble(e, thought);
      e.bubbleTimer?.remove();
      e.bubbleTimer = this.time.delayedCall(7000, () => { if (this.registry.get(SCENE_REG.selected) !== e.id) this.setBubble(e, ''); });
    } else if (!thought && this.registry.get(SCENE_REG.selected) !== e.id) this.setBubble(e, '');

    const target = standPoint(a.station, slot);
    const moved = e.station !== a.station || Math.abs(e.root.x - target.x) > 2 || Math.abs(e.root.y - target.y) > 2;
    e.station = a.station;
    if (moved) this.walkTo(e, target.x, target.y, a.status);
    else this.settle(e);
  }

  private walkTo(e: Ent, x: number, y: number, status: AgentStatus) {
    e.tween?.stop();
    const sx = e.root.x, sy = e.root.y;
    const via = { x, y: sy }; // horizontal along the current row first, then vertical: a readable aisle path
    const seg = (fx: number, fy: number, tx: number, ty: number) => Math.hypot(tx - fx, ty - fy);
    const d1 = seg(sx, sy, via.x, via.y), d2 = seg(via.x, via.y, x, y);
    const total = d1 + d2;
    if (total < 2) return this.settle(e);
    e.walking = true;
    const run = (tx: number, ty: number, dist: number, next?: () => void) => {
      if (dist < 2) return next?.();
      const dx = tx - e.root.x, dy = ty - e.root.y;
      e.facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : dy > 0 ? 'down' : 'up';
      this.play(e, 'walk');
      e.tween = this.tweens.add({ targets: e.root, x: tx, y: ty, duration: (dist / SPEED) * 1000, ease: 'Linear', onComplete: () => next?.() });
    };
    run(via.x, via.y, d1, () => run(x, y, d2, () => { e.walking = false; this.settle(e); }));
    void status;
  }

  private settle(e: Ent) {
    if (e.walking) return;
    if (e.status === 'asleep') {
      e.facing = 'down';
      this.play(e, 'sleep');
    } else {
      e.facing = e.station === 'arena_door' ? 'right' : e.station === 'door' ? 'up' : e.station === 'lawn' ? 'down' : 'up';
      this.play(e, 'idle');
    }
  }

  private drawRing(e: Ent) {
    e.ring.clear();
    const c = STATUS_COLOR[e.status];
    e.ring.fillStyle(0x181818, 1).fillRect(-40, 8, 8, 8).fillStyle(c, 1).fillRect(-38, 10, 4, 4);
  }

  private bubbleFrame(text: string, maxW: number, color = 0xf8f8d0) {
    const t = this.add.text(0, 0, text, { fontFamily: FONT_BODY, fontSize: '13px', fontStyle: 'bold', color: '#181818', wordWrap: { width: maxW }, lineSpacing: 2 }).setResolution(2);
    const w = Math.ceil(t.width) + 18, h = Math.ceil(t.height) + 14;
    const g = this.add.graphics();
    g.fillStyle(PAL.ink, 1).fillRect(-w / 2 - 3, -h - 3, w + 6, h + 6);
    g.fillStyle(color, 1).fillRect(-w / 2, -h, w, h);
    g.fillStyle(PAL.ink, 1).fillTriangle(-8, 3, 8, 3, 0, 14);
    g.fillStyle(color, 1).fillTriangle(-5, 0, 5, 0, 0, 9);
    t.setPosition(-w / 2 + 9, -h + 7);
    return { g, t, h };
  }

  private setBubble(e: Ent, text: string) {
    const clip = text.length > 96 ? text.slice(0, 94) + '…' : text;
    if (clip === e.bubbleText) return;
    e.bubbleText = clip;
    e.bubble?.destroy();
    e.bubble = null;
    if (!clip) return;
    const { g, t, h } = this.bubbleFrame(clip, 210);
    const c = this.add.container(e.root.x, e.root.y - 72, [g, t]).setDepth(800);
    c.setData('h', h).setData('w', Math.ceil(t.width) + 18);
    e.bubble = c;
  }

  private refreshSelection() {
    const sel = this.registry.get(SCENE_REG.selected) as string | null;
    this.ents.forEach((e) => {
      e.sel.clear();
      if (e.id === sel) {
        e.sel.lineStyle(4, PAL.yellow, 1).strokeEllipse(0, 0, 70, 24);
        e.sel.lineStyle(2, PAL.ink, 1).strokeEllipse(0, 0, 78, 30);
        e.root.setScale(1.04);
        e.plate.setVisible(true);
        this.setBubble(e, e.thought);
      } else {
        e.root.setScale(1);
        e.plate.setVisible(e.status !== 'asleep');
        if (!e.bubbleTimer || e.bubbleTimer.getProgress() >= 1) this.setBubble(e, '');
      }
    });
  }

  private refreshOak() {
    const text = (this.registry.get(SCENE_REG.oakSay) as string | undefined) ?? '';
    if (text === this.oakText) return;
    this.oakText = text;
    this.oakBubble?.destroy();
    this.oakBubble = null;
    if (!text) return;
    const { g, t } = this.bubbleFrame(text, 250, 0xfff7c0);
    this.oakBubble = this.add.container(OAK_HOME.x, OAK_HOME.y - 104, [g, t]).setDepth(800);
    this.oakBubble.setAlpha(0);
    this.tweens.add({ targets: this.oakBubble, alpha: 1, y: OAK_HOME.y - 108, duration: 220 });
  }

  /** For the Shift+E honesty overlay: label an entity with the seq of the event that moved it. */
  tagSeq(id: string, seq: number) {
    this.ents.get(id)?.seqTag.setText(`#${seq}`);
  }

  get stations() {
    return STATIONS;
  }
}
