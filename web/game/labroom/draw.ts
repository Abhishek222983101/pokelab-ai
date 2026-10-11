/**
 * Procedural drawing for Oak's Lab. Everything is rectangles on a 4px grid with a stepped edge, the same
 * construction language as the DOM panels, so the world and the console read as one handheld.
 */
import * as Phaser from 'phaser';
import { H, STATIONS, TILE, W, WALL_H } from './layout';

export const PAL = {
  ink: 0x181818,
  navy: 0x183088,
  navyDeep: 0x0e1c5c,
  gold: 0xd8a830,
  goldDeep: 0xa07818,
  yellow: 0xf8d858,
  cream: 0xf8f8d0,
  creamDeep: 0xe6e4b0,
  slate: 0x484878,
  slateSoft: 0x7878a8,
  red: 0xe84040,
  green: 0x58d858,
  sky: 0x94c6fc,
  floorA: 0xd6def2,
  floorB: 0xc9d3ec,
  wall: 0x22408f,
  wallDark: 0x1b3680,
  wood: 0xb07838,
  woodDark: 0x7a4e22,
  woodLight: 0xd09a58,
  metal: 0x8890a8,
  metalDark: 0x585e78,
};

/** Rect with a 4px ink edge and a 4px bottom lip: the "keycap" look. */
export function block(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number, fill: number, lip?: number, edge: number = PAL.ink) {
  g.fillStyle(edge, 1).fillRect(x - 4, y - 4, w + 8, h + 8);
  g.fillStyle(fill, 1).fillRect(x, y, w, h);
  if (lip !== undefined) g.fillStyle(lip, 1).fillRect(x, y + h - 8, w, 8);
}

export function drawFloor(g: Phaser.GameObjects.Graphics) {
  for (let r = 0; r * TILE < H; r++) {
    for (let c = 0; c * TILE < W; c++) {
      const x = c * TILE, y = WALL_H + r * TILE;
      g.fillStyle((r + c) % 2 ? PAL.floorA : PAL.floorB, 1).fillRect(x, y, TILE, TILE);
      g.fillStyle(0xffffff, 0.35).fillRect(x, y, TILE, 2).fillRect(x, y, 2, TILE);
      g.fillStyle(0x6e7aa8, 0.12).fillRect(x, y + TILE - 2, TILE, 2);
    }
  }
}

export function drawWall(g: Phaser.GameObjects.Graphics) {
  g.fillStyle(PAL.wall, 1).fillRect(0, 0, W, WALL_H);
  // brick courses
  for (let r = 0; r < 6; r++) {
    g.fillStyle(PAL.wallDark, 1).fillRect(0, r * 24 + 22, W, 2);
    for (let c = -1; c < W / 48 + 1; c++) g.fillRect(c * 48 + (r % 2 ? 24 : 0), r * 24, 2, 22);
  }
  g.fillStyle(0xffffff, 0.06).fillRect(0, 0, W, 6);
  // wainscot + gold trim
  g.fillStyle(PAL.navyDeep, 1).fillRect(0, WALL_H - 28, W, 28);
  g.fillStyle(PAL.gold, 1).fillRect(0, WALL_H - 32, W, 4);
  g.fillStyle(PAL.yellow, 1).fillRect(0, WALL_H - 32, W, 2);
  g.fillStyle(PAL.ink, 0.35).fillRect(0, WALL_H, W, 6);
}

function windowPane(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number) {
  block(g, x, y, w, h, PAL.sky, undefined, PAL.cream);
  g.fillStyle(0xe2f0ff, 1).fillRect(x, y, w, h / 3);
  g.fillStyle(0xffffff, 0.8).fillRect(x + 8, y + 8, 22, 6).fillRect(x + w - 40, y + 20, 26, 6);
  g.fillStyle(PAL.cream, 1).fillRect(x + w / 2 - 2, y, 4, h).fillRect(x, y + h / 2 - 2, w, 4);
}

export function drawWindows(g: Phaser.GameObjects.Graphics) {
  windowPane(g, 340, 28, 72, 70);
  windowPane(g, 548, 28, 72, 70);
}

function labelPlate(scene: Phaser.Scene, x: number, y: number, text: string) {
  const t = scene.add.text(x, y, text, { fontFamily: '"Press Start 2P"', fontSize: '8px', color: '#f8f8d0' }).setOrigin(0.5).setResolution(2);
  const g = scene.add.graphics();
  const w = t.width + 14, h = 18;
  g.fillStyle(PAL.gold, 1).fillRect(x - w / 2 - 3, y - h / 2 - 3, w + 6, h + 6);
  g.fillStyle(PAL.navy, 1).fillRect(x - w / 2, y - h / 2, w, h);
  g.fillStyle(0xffffff, 0.9).fillRect(x - w / 2, y - h / 2, w, 2);
  g.setDepth(0.5);
  t.setDepth(0.6);
}

function shelf(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number) {
  block(g, x, y, w, 108, PAL.woodDark, PAL.ink);
  const cols = [0xe84040, 0x6890f0, 0xf8d858, 0x78c850, 0xf85888, 0xf8f8d0, 0xa890f0];
  for (let row = 0; row < 3; row++) {
    const by = y + 8 + row * 32;
    g.fillStyle(PAL.wood, 1).fillRect(x + 4, by + 24, w - 8, 4);
    let bx = x + 8;
    let i = row * 3;
    while (bx < x + w - 16) {
      const bw = 8 + ((i * 7) % 3) * 4, bh = 16 + ((i * 5) % 3) * 4;
      g.fillStyle(cols[i % cols.length], 1).fillRect(bx, by + 24 - bh, bw, bh);
      g.fillStyle(0xffffff, 0.35).fillRect(bx, by + 24 - bh, 2, bh);
      bx += bw + 2; i++;
    }
  }
}

function table(g: Phaser.GameObjects.Graphics, cx: number, by: number, w: number) {
  block(g, cx - w / 2, by - 36, w, 28, PAL.woodLight, PAL.wood);
  g.fillStyle(PAL.woodDark, 1).fillRect(cx - w / 2 + 6, by - 8, 8, 20).fillRect(cx + w / 2 - 14, by - 8, 8, 20);
  g.fillStyle(0xffffff, 0.3).fillRect(cx - w / 2, by - 36, w, 3);
}

function monitor(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number, kind: 'code' | 'chart' | 'doc') {
  block(g, x, y, w, h, 0x10183c, undefined, PAL.metalDark);
  g.fillStyle(0x1f2c6a, 1).fillRect(x + 4, y + 4, w - 8, h - 8);
  if (kind === 'code') {
    const cs = [0xf8d858, 0x58d858, 0x94c6fc, 0xf85888];
    for (let i = 0; i < Math.floor((h - 12) / 8); i++) g.fillStyle(cs[i % 4], 1).fillRect(x + 8 + (i % 3) * 6, y + 8 + i * 8, 12 + ((i * 11) % 28), 3);
  } else if (kind === 'chart') {
    g.fillStyle(0x58d858, 1);
    for (let i = 0; i < w - 16; i += 4) g.fillRect(x + 8 + i, y + h - 10 - Math.floor(((h - 24) / (1 + Math.exp(-(i - (w - 16) * 0.6) / 6)))), 4, 3);
    g.fillStyle(0xf8d858, 1).fillRect(x + 8, y + h - 12, w - 16, 2);
  } else {
    g.fillStyle(PAL.cream, 1).fillRect(x + 10, y + 10, w - 20, 3).fillRect(x + 10, y + 18, w - 28, 3).fillRect(x + 10, y + 26, w - 20, 3);
  }
  g.fillStyle(PAL.metalDark, 1).fillRect(x + w / 2 - 6, y + h + 4, 12, 8).fillRect(x + w / 2 - 14, y + h + 10, 28, 4);
}

export interface LedSpec { x: number; y: number; color: number }

/** Draws the static furniture; returns blinking LED positions for the scene to animate. */
export function drawFurniture(scene: Phaser.Scene): LedSpec[] {
  const g = scene.add.graphics().setDepth(0.3);
  const leds: LedSpec[] = [];
  const S = STATIONS;

  // library: two shelves + reading table + open book
  shelf(g, 60, 20, 100);
  shelf(g, 176, 20, 100);
  table(g, S.library_desk.x, S.library_desk.y, 150);
  g.fillStyle(PAL.cream, 1).fillRect(S.library_desk.x - 26, S.library_desk.y - 52, 22, 16).fillRect(S.library_desk.x + 4, S.library_desk.y - 52, 22, 16);
  g.fillStyle(PAL.slate, 1).fillRect(S.library_desk.x - 4, S.library_desk.y - 54, 8, 18);
  g.fillStyle(PAL.red, 1).fillRect(S.library_desk.x + 44, S.library_desk.y - 50, 14, 14);

  // quest board (wall-mounted easel)
  const qx = S.quest_board.x;
  block(g, qx - 112, 44, 224, 124, PAL.woodDark, PAL.ink);
  g.fillStyle(0xe6d6a8, 1).fillRect(qx - 104, 52, 208, 100);
  const nodes = [[-80, 76], [-30, 76], [20, 76], [70, 76], [-55, 116], [45, 116]];
  g.lineStyle(3, PAL.slate, 1);
  const pairs = [[0, 1], [1, 2], [2, 3], [1, 4], [2, 5]];
  pairs.forEach(([a, b]) => g.lineBetween(qx + nodes[a][0], nodes[a][1], qx + nodes[b][0], nodes[b][1]));
  nodes.forEach(([dx, dy], i) => {
    const done = i < 2, running = i === 2 || i === 4;
    g.fillStyle(PAL.ink, 1).fillRect(qx + dx - 14, dy - 14, 28, 28);
    g.fillStyle(done ? PAL.green : running ? PAL.yellow : PAL.cream, 1).fillRect(qx + dx - 10, dy - 10, 20, 20);
  });
  g.fillStyle(PAL.red, 1).fillRect(qx - 100, 54, 8, 8);

  // analysis table + wall monitors
  monitor(g, 700, 36, 88, 56, 'chart');
  monitor(g, 800, 36, 88, 56, 'doc');
  table(g, S.analysis_table.x, S.analysis_table.y, 170);
  g.fillStyle(0xa890f0, 1).fillCircle(S.analysis_table.x + 50, S.analysis_table.y - 46, 12);
  g.fillStyle(0xffffff, 0.5).fillCircle(S.analysis_table.x + 46, S.analysis_table.y - 50, 4);

  // code bench: two monitors + keyboard
  table(g, S.code_bench.x, S.code_bench.y, 170);
  monitor(g, S.code_bench.x - 76, S.code_bench.y - 96, 64, 44, 'code');
  monitor(g, S.code_bench.x + 12, S.code_bench.y - 96, 64, 44, 'code');
  g.fillStyle(PAL.metal, 1).fillRect(S.code_bench.x - 28, S.code_bench.y - 46, 56, 8);

  // server racks
  for (let i = 0; i < 2; i++) {
    const rx = S.server_rack.x - 62 + i * 76, ry = S.server_rack.y - 120;
    block(g, rx, ry, 64, 120, PAL.metalDark, PAL.ink);
    for (let k = 0; k < 6; k++) {
      g.fillStyle(PAL.metal, 1).fillRect(rx + 6, ry + 8 + k * 17, 52, 13);
      g.fillStyle(0x10183c, 1).fillRect(rx + 10, ry + 12 + k * 17, 24, 5);
      leds.push({ x: rx + 46, y: ry + 14 + k * 17, color: k % 3 === 0 ? 0xf8d858 : 0x58d858 });
    }
  }

  // scribe desk with paper stack and quill
  table(g, S.scribe_desk.x, S.scribe_desk.y, 150);
  g.fillStyle(PAL.cream, 1).fillRect(S.scribe_desk.x - 36, S.scribe_desk.y - 50, 30, 14).fillRect(S.scribe_desk.x - 32, S.scribe_desk.y - 56, 30, 8);
  g.fillStyle(PAL.ink, 1).fillRect(S.scribe_desk.x + 22, S.scribe_desk.y - 60, 4, 26);
  g.fillStyle(PAL.red, 1).fillRect(S.scribe_desk.x + 16, S.scribe_desk.y - 66, 8, 10);

  // arena door (right wall)
  const ax = W - 52, ay = 262;
  block(g, ax, ay, 52, 140, PAL.metalDark, PAL.ink);
  g.fillStyle(PAL.navy, 1).fillRect(ax + 8, ay + 8, 36, 112);
  g.fillStyle(PAL.yellow, 1);
  for (let k = 0; k < 4; k++) g.fillTriangle(ax + 14, ay + 22 + k * 26, ax + 38, ay + 34 + k * 26, ax + 14, ay + 46 + k * 26);

  // Oak's rug with a Poké Ball seal
  const rx = 480, ry = 392;
  g.fillStyle(PAL.ink, 0.18).fillEllipse(rx, ry + 8, 288, 136);
  g.fillStyle(PAL.navy, 1).fillEllipse(rx, ry, 280, 128);
  g.fillStyle(PAL.gold, 1).fillEllipse(rx, ry, 256, 108);
  g.fillStyle(PAL.navyDeep, 1).fillEllipse(rx, ry, 244, 98);
  g.fillStyle(PAL.ink, 1).fillCircle(rx, ry, 44);
  g.fillStyle(PAL.cream, 1).beginPath().arc(rx, ry, 40, 0, Math.PI, false).closePath().fillPath();
  g.fillStyle(PAL.red, 1).beginPath().arc(rx, ry, 40, Math.PI, 0, false).closePath().fillPath();
  g.fillStyle(PAL.ink, 1).fillRect(rx - 40, ry - 4, 80, 8).fillCircle(rx, ry, 13);
  g.fillStyle(PAL.cream, 1).fillCircle(rx, ry, 7);

  // rest rug
  g.fillStyle(PAL.ink, 0.15).fillRect(660, 532, 220, 100);
  block(g, 656, 524, 220, 96, 0x5aa85a, 0x3f8a43);
  for (let k = 0; k < 3; k++) {
    g.fillStyle(0xf8f8d0, 1).fillRect(676 + k * 70, 534, 44, 22);
    g.fillStyle(0xffffff, 0.6).fillRect(678 + k * 70, 536, 40, 4);
  }

  // front door + mat
  block(g, 440, H - 20, 80, 24, PAL.woodDark, undefined);
  g.fillStyle(PAL.red, 1).fillRect(452, H - 22, 56, 6);
  block(g, 436, H - 52, 88, 20, PAL.slate, undefined, PAL.ink);

  // potted plants
  [[40, 130], [920, 130], [40, 520]].forEach(([px, py]) => {
    g.fillStyle(PAL.ink, 1).fillRect(px - 14, py - 8, 28, 22);
    g.fillStyle(0xc86038, 1).fillRect(px - 10, py - 4, 20, 16);
    g.fillStyle(0x3f8a43, 1).fillCircle(px, py - 18, 14).fillCircle(px - 10, py - 10, 9).fillCircle(px + 10, py - 10, 9);
    g.fillStyle(0x78c850, 1).fillCircle(px - 3, py - 21, 6);
  });

  // plates
  // Labels sit on/above the furniture, never in the aisle where agents stand and carry their own nameplates.
  const labelAt: Record<keyof typeof S, [number, number]> = {
    library_desk: [S.library_desk.x, S.library_desk.y - 22],
    quest_board: [S.quest_board.x, 186],
    analysis_table: [S.analysis_table.x, S.analysis_table.y - 22],
    code_bench: [S.code_bench.x, S.code_bench.y - 22],
    server_rack: [S.server_rack.x - 96, S.server_rack.y - 84],
    arena_door: [W - 90, 246],
    scribe_desk: [S.scribe_desk.x, S.scribe_desk.y - 22],
    lawn: [S.lawn.x, 508],
    door: [S.door.x, H - 92],
  };
  (Object.keys(S) as Array<keyof typeof S>).forEach((k) => labelPlate(scene, labelAt[k][0], labelAt[k][1], S[k].label));

  return leds;
}

/** Soft light shafts from the windows + a dusk-tinted vignette: depth for almost nothing. */
export function drawLight(scene: Phaser.Scene) {
  const g = scene.add.graphics().setDepth(900).setAlpha(0.9);
  g.fillStyle(0xffffff, 0.09);
  g.fillPoints([new Phaser.Math.Vector2(346, 98), new Phaser.Math.Vector2(406, 98), new Phaser.Math.Vector2(470, 400), new Phaser.Math.Vector2(330, 400)], true);
  g.fillPoints([new Phaser.Math.Vector2(554, 98), new Phaser.Math.Vector2(614, 98), new Phaser.Math.Vector2(630, 400), new Phaser.Math.Vector2(490, 400)], true);
  const v = scene.add.graphics().setDepth(901);
  for (let i = 0; i < 6; i++) {
    v.lineStyle(24, 0x0e1c5c, 0.05 + i * 0.012);
    v.strokeRect(i * 20 - 10, i * 20 - 10, W - i * 40 + 20, H - i * 40 + 20);
  }
  scene.tweens.add({ targets: g, alpha: 0.55, duration: 3200, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
}
