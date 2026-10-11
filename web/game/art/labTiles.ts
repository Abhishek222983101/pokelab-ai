/**
 * PokéLab's additions to the PokeStonks procedural tileset (GAME-DESIGN.md §2.1): building styles
 * (Oak's Lab, Pokémon Center, Library, Gym), their wall plaques, and Oak's Lab furniture. Kept in
 * our own file so the forked engine files stay diffable against PokeStonks. Buildings reuse the
 * engine's own roof/wall/window/door painters with a theme override, so every style inherits the
 * same shading, outlines and gable silhouettes as the original buildings.
 */
import { PixelGrid, hex, mix, lighten, darken, rgba, makeRamp, hash2, type Color, type Ramp } from './pixel';
import { Painter } from './paint';
import type { ThemePal } from './themes';
import * as P from './tileProps';

const T = 16;
const WHITE = hex('#ffffff');
const INK = hex('#1a1226');

/* ------------------------------------------------------------------ building styles ---- */

export type BuildingStyle = 'lab' | 'center' | 'library' | 'gym';

/** The town theme with the roof/wall/glass swapped for a building style. */
export function styledTheme(th: ThemePal, style: BuildingStyle): ThemePal {
  switch (style) {
    case 'lab':
      return {
        ...th,
        roof: { style: 'metal', ramp: makeRamp('#5878b0'), alt: makeRamp('#3c5890') },
        wall: { style: 'stucco', ramp: makeRamp('#eceef4'), trim: makeRamp('#64749a') },
        glass: makeRamp('#8ccff4'),
      };
    case 'center':
      return {
        ...th,
        roof: { style: 'metal', ramp: makeRamp('#e0403a'), alt: makeRamp('#fbf2ea') },
        wall: { style: 'panel', ramp: makeRamp('#f2f2f6'), trim: makeRamp('#c83c3c') },
        glass: makeRamp('#94d6f8'),
      };
    case 'library':
      return {
        ...th,
        roof: { style: 'shingle', ramp: makeRamp('#3c8a68'), alt: makeRamp('#2a6a50') },
        wall: { style: 'brick', ramp: makeRamp('#d6b48c'), trim: makeRamp('#6a4a2c') },
      };
    case 'gym':
      return {
        ...th,
        roof: { style: 'metal', ramp: makeRamp('#687088'), alt: makeRamp('#d8a830') },
        wall: { style: 'marble', ramp: makeRamp('#d8dae4'), trim: makeRamp('#8a6a28') },
        glass: makeRamp('#b8c8f0'),
      };
  }
}

/** Roof tile in a building style; gyms get a gold ridge cap and gold eave trim. */
export function paintStyledRoof(g: PixelGrid, th: ThemePal, style: BuildingStyle, part: 'l' | 'm' | 'r', row: 'ridge' | 'eave') {
  const s = styledTheme(th, style);
  P.paintRoof(g, s, part, row);
  if (style === 'gym' || style === 'center') {
    // gym: gold ridge + eave trim; Pokémon Center: white ridge + eave band (alt ramp is white)
    const gold = s.roof.alt;
    if (row === 'ridge') {
      for (let x = 0; x < T; x++) {
        if (g.get(x, 0) === 0) continue;
        g.set(x, 0, gold.hi); if (g.get(x, 1) !== 0) g.set(x, 1, gold.mid);
        if (g.get(x, 2) !== 0) g.set(x, 2, gold.sh);
      }
    } else {
      for (let x = 0; x < T; x++) { g.set(x, 12, gold.mid); g.set(x, 13, gold.sh); }
    }
  }
}

export function paintStyledWall(g: PixelGrid, th: ThemePal, style: BuildingStyle) { P.paintWall(g, styledTheme(th, style)); }
export function paintStyledWindow(g: PixelGrid, th: ThemePal, style: BuildingStyle) { P.paintWindow(g, styledTheme(th, style)); }

export function paintStyledDoor(g: PixelGrid, th: ThemePal, style: BuildingStyle) {
  const s = styledTheme(th, style);
  if (style !== 'center' && style !== 'lab') { P.paintDoor(g, s); return; }
  // automatic glass sliding doors (Pokémon Center / Lab)
  P.paintWall(g, s);
  const f = s.wall.trim, gl = s.glass;
  g.rect(2, 1, 12, 15, f.deep);
  g.rect(3, 2, 10, 14, gl.mid);
  for (let y = 2; y < 16; y++) for (let x = 3; x < 13; x++) if ((x - y + 32) % 6 === 0) g.set(x, y, gl.hi);
  g.rect(3, 2, 10, 1, gl.hi);
  g.vline(7, 2, 14, f.mid); g.vline(8, 2, 14, f.sh);
  g.set(6, 9, f.hi); g.set(9, 9, f.hi);
  g.rect(1, 14, 14, 2, mix(f.mid, WHITE, 0.35)); g.hline(1, 15, 14, f.sh);
}

/* ------------------------------------------------------------------ plaques ---- */

export type PlateKind = 'pokeball' | 'crest' | 'flask' | 'book' | 'egg' | 'monitor';

const PLATE_STYLE: Record<PlateKind, BuildingStyle> = {
  pokeball: 'center', crest: 'gym', flask: 'lab', book: 'library', egg: 'library', monitor: 'lab',
};

/** Wall tile with a framed sign plate and an emblem — the building's identity at a glance. */
export function paintPlate(g: PixelGrid, th: ThemePal, kind: PlateKind, style: BuildingStyle = PLATE_STYLE[kind]) {
  const s = styledTheme(th, style);
  P.paintWall(g, s);
  const frame = kind === 'crest' ? makeRamp('#d8a830') : s.wall.trim;
  const field = kind === 'pokeball' ? makeRamp('#f6f6fa') : kind === 'crest' ? makeRamp('#2a3060') : makeRamp('#183088');
  g.rect(1, 2, 14, 11, frame.deep);
  g.rect(2, 3, 12, 9, field.mid);
  g.hline(2, 3, 12, field.hi);
  g.hline(1, 2, 14, frame.hi);
  g.rect(1, 13, 14, 1, rgba(10, 6, 24, 90));
  const p = new Painter(g);
  switch (kind) {
    case 'pokeball': {
      const red = makeRamp('#e0403a');
      for (let y = 4; y <= 11; y++) for (let x = 4; x <= 11; x++) {
        const d = Math.hypot(x - 7.5, y - 7.5);
        if (d > 3.9) continue;
        g.set(x, y, y < 7 ? (d < 2.8 ? red.mid : red.sh) : d < 2.8 ? WHITE : hex('#c8c8d4'));
      }
      g.hline(4, 7, 8, INK); g.hline(4, 8, 8, INK);
      g.rect(6, 6, 4, 4, INK); g.rect(7, 7, 2, 2, WHITE);
      g.set(5, 5, lighten(red.mid, 0.5));
      break;
    }
    case 'crest': {
      const gold = makeRamp('#f0c040');
      p.flat([[7.5, 3.5], [12, 5.5], [11, 10], [7.5, 12], [4, 10], [3, 5.5]], gold.mid, gold.line);
      g.vline(7, 5, 6, gold.hi); g.vline(8, 5, 6, gold.sh);
      g.hline(5, 7, 6, gold.hi);
      g.set(7, 4, WHITE);
      break;
    }
    case 'flask': {
      const glass = hex('#d8eef8'), liquid = makeRamp('#58d858');
      g.rect(7, 4, 2, 3, glass); g.hline(6, 4, 4, hex('#a8c8d8'));
      p.flat([[6.5, 6.5], [9.5, 6.5], [12, 11.5], [4, 11.5]], glass, hex('#7898b0'));
      for (let y = 9; y <= 10; y++) for (let x = 5; x <= 10; x++) if (g.get(x, y) === glass) g.set(x, y, y === 9 ? liquid.hi : liquid.mid);
      g.set(7, 9, WHITE); g.set(9, 8, hex('#a8ffa8'));
      break;
    }
    case 'book': {
      const page = hex('#f8f4e4'), cover = makeRamp('#c84040');
      g.rect(3, 5, 10, 6, cover.mid); g.rect(4, 5, 4, 5, page); g.rect(8, 5, 4, 5, page);
      g.vline(8, 5, 6, cover.sh);
      for (const y of [6, 8]) { g.hline(5, y, 2, hex('#9898b0')); g.hline(9, y, 2, hex('#9898b0')); }
      g.hline(3, 10, 10, cover.deep);
      break;
    }
    case 'egg': {
      const shell = makeRamp('#f6f0d8');
      p.disc(7.5, 7.8, 3.2, 4, shell.mid, shell.line);
      g.set(6, 6, WHITE); g.set(7, 5, shell.hi);
      g.set(8, 8, hex('#58b058')); g.set(6, 9, hex('#58b058')); g.set(9, 10, hex('#58b058'));
      break;
    }
    case 'monitor': {
      g.rect(4, 4, 8, 6, hex('#20283c')); g.rect(5, 5, 6, 4, hex('#3ad8c8'));
      g.hline(5, 6, 4, hex('#a8fff0')); g.hline(5, 8, 3, hex('#a8fff0'));
      g.rect(7, 10, 2, 1, hex('#5a6280')); g.hline(5, 11, 6, hex('#5a6280'));
      break;
    }
  }
}

/* ------------------------------------------------------------------ Oak's Lab furniture ---- */

/** Desk front + top, painted over the floor. `top` = how many px of floor stay visible above. */
function deskBody(g: PixelGrid, wood: Ramp, part: 'l' | 'r' | 'single', top = 5) {
  const x0 = part === 'r' ? 0 : 1, x1 = part === 'l' ? 16 : 15;
  g.rect(x0, top, x1 - x0, 4, lighten(wood.hi, 0.1));
  g.hline(x0, top, x1 - x0, lighten(wood.hi, 0.35));
  g.rect(x0, top + 4, x1 - x0, 15 - top - 4, wood.mid);
  g.hline(x0, top + 4, x1 - x0, wood.deep);
  for (let x = x0 + 2; x < x1 - 2; x += 6) g.rect(x, top + 6, 4, 3, wood.sh);
  g.hline(x0, 15, x1 - x0, wood.deep);
  if (part !== 'r') g.vline(x0, top, 16 - top, wood.line);
  if (part !== 'l') g.vline(x1 - 1, top, 16 - top, wood.line);
}

/** Research desk with a monitor showing code (left) / keyboard, notes and a mug (right). */
export function paintDesk(g: PixelGrid, th: ThemePal, part: 'l' | 'r') {
  P.paintFloor(g, th, false);
  P.softShadow(g, part === 'l' ? 9 : 7, 15.2, 7.5, 1.4, 55);
  const wood = makeRamp('#9a6a3c');
  deskBody(g, wood, part, 7);
  if (part === 'l') {
    const bez = makeRamp('#2c3448');
    g.rect(3, 0, 11, 8, bez.mid); g.rect(3, 0, 11, 1, bez.hi);
    g.rect(4, 1, 9, 5, hex('#10202c'));
    const code = [hex('#58d8a8'), hex('#f8d858'), hex('#88b8ff')];
    for (let r = 0; r < 4; r++) {
      const len = 2 + Math.floor(hash2(r, 3, 7) * 6);
      g.hline(5 + (r === 1 || r === 2 ? 1 : 0), 2 + r, len, code[r % 3]);
    }
    g.rect(7, 8, 3, 1, bez.deep);
  } else {
    g.rect(1, 6, 8, 2, hex('#d8dce8')); g.hline(1, 6, 8, WHITE);
    for (let x = 2; x < 9; x += 2) g.set(x, 7, hex('#9aa0b8'));
    g.rect(10, 3, 4, 4, hex('#f8f4e4')); g.hline(11, 4, 2, hex('#a0a0b8')); g.hline(11, 5, 2, hex('#a0a0b8'));
    const mug = makeRamp('#e04a3c');
    g.rect(11, 6, 3, 2, mug.mid); g.set(14, 6, mug.sh); g.hline(11, 6, 3, mug.hi);
  }
}

/** 16x32 bookshelf: top half sits on the wall row, bottom half on the floor. */
export function paintBookshelf(th: ThemePal): PixelGrid {
  const g = new PixelGrid(T, 32);
  const top = new PixelGrid(T, T); P.paintIWall(top, th, 'mid');
  const bot = new PixelGrid(T, T); P.paintFloor(bot, th, false);
  g.blit(top, 0, 0); g.blit(bot, 0, 16);
  const wood = makeRamp('#7a4c2a');
  P.softShadow(g, 8, 31, 7.5, 1.2, 70);
  g.rect(1, 1, 14, 30, wood.deep);
  g.rect(2, 2, 12, 28, wood.sh);
  const spines = [hex('#c84a3c'), hex('#3c6ac8'), hex('#58a858'), hex('#e0b040'), hex('#8a58c0'), hex('#e8e4d8')];
  for (let shelf = 0; shelf < 4; shelf++) {
    const base = 8 + shelf * 7;
    g.hline(2, base, 12, wood.mid); g.hline(2, base + 1, 12, wood.deep);
    let x = 3;
    while (x < 13) {
      const w = hash2(x, shelf, 21) < 0.3 ? 2 : 1;
      const h = 4 + (hash2(x, shelf, 5) < 0.4 ? 1 : 0);
      const c = spines[Math.floor(hash2(x, shelf, 13) * spines.length)];
      g.rect(x, base - h, w, h, c);
      g.set(x, base - h, lighten(c, 0.35));
      if (w === 2) g.vline(x + 1, base - h + 1, h - 1, darken(c, 0.2));
      x += w + (hash2(x, shelf, 31) < 0.15 ? 1 : 0);
    }
  }
  g.hline(1, 1, 14, wood.hi);
  return g;
}

/** Quest board (plan DAG): cork board on the wall, note cards joined by string. 2 tiles wide. */
export function paintQuestBoard(g: PixelGrid, th: ThemePal, part: 'l' | 'r') {
  P.paintIWall(g, th, 'mid');
  const frame = makeRamp('#8a5a30'), cork = makeRamp('#c89a64');
  const x0 = part === 'l' ? 1 : 0, x1 = part === 'r' ? 15 : 16;
  g.rect(x0, 1, x1 - x0, 13, frame.mid);
  g.rect(x0 + (part === 'l' ? 1 : 0), 2, x1 - x0 - (part === 'l' ? 1 : 0) - (part === 'r' ? 1 : 0), 11, cork.mid);
  for (let y = 2; y < 13; y++) for (let x = x0; x < x1; x++) if (g.get(x, y) === cork.mid && hash2(x, y, part === 'l' ? 3 : 4) < 0.12) g.set(x, y, cork.sh);
  g.hline(x0, 1, x1 - x0, frame.hi); g.hline(x0, 13, x1 - x0, frame.deep);
  const card = (x: number, y: number, c: Color) => {
    g.rect(x, y, 4, 3, hex('#f8f4e4')); g.hline(x, y, 4, c); g.set(x + 1, y + 1, hex('#a0a0b8')); g.set(x + 2, y + 1, hex('#a0a0b8'));
    g.set(x + 1, y - 1 < 2 ? y : y - 1, hex('#e04040'));
  };
  const string = hex('#d84040');
  if (part === 'l') {
    g.line(5, 5, 14, 4, string); g.line(5, 5, 9, 10, string); g.line(9, 10, 16, 9, string);
    card(3, 4, hex('#58a8e8')); card(8, 9, hex('#58c858'));
  } else {
    g.line(0, 4, 4, 4, string); g.line(0, 9, 8, 7, string); g.line(4, 4, 8, 7, string);
    card(2, 3, hex('#f0c040')); card(7, 6, hex('#c858c8'));
  }
}

/** Analysis table: charts on paper (one of them a grokking-shaped curve) and a magnifier. */
export function paintAnalysisTable(g: PixelGrid, th: ThemePal, part: 'l' | 'r') {
  P.paintFloor(g, th, false);
  P.softShadow(g, part === 'l' ? 9 : 7, 15.2, 7.5, 1.4, 55);
  deskBody(g, makeRamp('#6a7488'), part, 4);
  const paper = hex('#f8f4e4');
  if (part === 'l') {
    g.rect(2, 2, 10, 6, paper); g.hline(2, 2, 10, WHITE);
    g.vline(3, 3, 4, hex('#a0a0b8')); g.hline(3, 6, 8, hex('#a0a0b8'));
    // delayed generalisation: flat, then a sudden jump
    const curve: Array<[number, number]> = [[4, 6], [5, 6], [6, 6], [7, 5], [8, 6], [9, 3], [10, 3]];
    for (const [x, y] of curve) g.set(x, y, hex('#e04040'));
    g.set(9, 4, hex('#e04040'));
  } else {
    g.rect(1, 3, 7, 5, paper);
    for (let i = 0; i < 4; i++) g.rect(2 + i * 1.5 | 0, 7 - (i + 1), 1, i + 1, [hex('#58a8e8'), hex('#58c858'), hex('#f0c040'), hex('#c858c8')][i]);
    const rim = makeRamp('#b8a070');
    new Painter(g).disc(11.5, 4.5, 2.2, 2.2, hex('#c8e8f8'), rim.deep);
    g.set(11, 4, WHITE);
    g.line(13, 6, 15, 8, rim.mid);
  }
}

/** Scribe desk: open notebook, quill and inkpot (notes / reports / author emails). */
export function paintScribeDesk(g: PixelGrid, th: ThemePal) {
  P.paintFloor(g, th, false);
  P.softShadow(g, 8, 15.2, 7, 1.4, 55);
  deskBody(g, makeRamp('#8a5a34'), 'single', 6);
  const page = hex('#f8f4e4');
  g.rect(2, 3, 6, 5, page); g.rect(8, 3, 5, 5, page); g.vline(8, 3, 5, hex('#c8c0a8'));
  for (const y of [4, 6]) { g.hline(3, y, 4, hex('#8a8aa8')); g.hline(9, y, 3, hex('#8a8aa8')); }
  g.rect(12, 6, 2, 2, INK); g.set(12, 6, hex('#5a5a80'));
  g.line(12, 1, 14, 5, hex('#f8f8f8')); g.set(14, 5, INK);
}

/** 16x32 Pokédex terminal (memory): red cabinet, glowing screen, buttons. Stands on the floor. */
export function paintDexTerminal(th: ThemePal): PixelGrid {
  const g = new PixelGrid(T, 32);
  const bot = new PixelGrid(T, T); P.paintFloor(bot, th, false);
  g.blit(bot, 0, 16);
  const body = makeRamp('#d83c38');
  P.softShadow(g, 8, 31, 7, 1.4, 70);
  g.rect(2, 4, 12, 26, body.mid);
  g.rect(2, 4, 12, 1, body.hi); g.rect(2, 4, 1, 26, body.hi); g.rect(13, 4, 1, 26, body.deep); g.rect(2, 29, 12, 1, body.deep);
  // hinge band like the handheld
  g.rect(2, 15, 12, 2, body.deep); g.hline(2, 15, 12, body.sh);
  // screen
  g.rect(4, 6, 8, 7, hex('#1c2a24')); g.rect(5, 7, 6, 5, hex('#68e8a8'));
  for (let y = 7; y < 12; y++) if (y % 2 === 0) g.hline(5, y, 6, hex('#9cf8c8'));
  g.set(5, 7, WHITE);
  // lens + buttons
  new Painter(g).disc(4.5, 2.5, 1.6, 1.6, hex('#58b8f8'), body.line); g.set(4, 2, WHITE);
  g.set(8, 2, hex('#f8d040')); g.set(10, 2, hex('#58d858'));
  g.rect(4, 19, 3, 3, hex('#202838')); g.rect(9, 19, 3, 2, hex('#f8f8f8')); g.rect(9, 22, 3, 2, hex('#f8f8f8'));
  for (let x = 4; x < 12; x += 2) g.set(x, 26, body.sh);
  g.outline(body.line);
  return g;
}

/** Arena door (to the Gym battles), 2 tiles wide on the wall row, Poké Ball across both halves. */
export function paintArenaDoor(g: PixelGrid, th: ThemePal, part: 'l' | 'r') {
  P.paintIWall(g, th, 'mid');
  const gold = makeRamp('#d8a830'), steel = makeRamp('#5a6480');
  const x0 = part === 'l' ? 2 : 0, x1 = part === 'r' ? 14 : 16;
  g.rect(x0, 0, x1 - x0, 16, gold.deep);
  g.rect(x0 + (part === 'l' ? 1 : 0), 1, x1 - x0 - 1, 15, steel.mid);
  for (let y = 1; y < 16; y += 3) g.hline(x0 + (part === 'l' ? 1 : 0), y, x1 - x0 - 1, steel.sh);
  if (part === 'l') g.vline(15, 1, 15, steel.deep); else g.vline(0, 1, 15, steel.hi);
  // ball emblem centred on the seam (x = 16 of the pair)
  const cx = part === 'l' ? 16 : 0;
  for (let y = 4; y <= 11; y++) for (let x = 0; x < T; x++) {
    const d = Math.hypot(x + 0.5 - cx, y + 0.5 - 8);
    if (d > 4.2) continue;
    g.set(x, y, d > 3.4 ? INK : y < 8 ? hex('#e0403a') : WHITE);
  }
  for (let x = 0; x < T; x++) if (Math.abs(x + 0.5 - cx) < 4) g.set(x, 8, INK);
  for (let x = 0; x < T; x++) { const d = Math.abs(x + 0.5 - cx); if (d < 1.6) { g.set(x, 7, WHITE); g.set(x, 9, WHITE); } }
  g.hline(x0, 0, x1 - x0, gold.hi);
}

/** Oak's table with three Poké Balls. */
export function paintBallTable(g: PixelGrid, th: ThemePal) {
  P.paintFloor(g, th, false);
  P.softShadow(g, 8, 14.6, 6.6, 1.6, 60);
  const wood = makeRamp('#b07a48');
  const tp = new Painter(g);
  tp.disc(8, 9, 7, 4.2, wood.sh, wood.line);
  tp.disc(8, 8, 7, 4.2, wood.mid, wood.line);
  g.hline(3, 5, 10, wood.hi);
  for (const bx of [4, 8, 12]) {
    for (let y = 5; y <= 8; y++) for (let x = bx - 2; x <= bx + 1; x++) {
      const d = Math.hypot(x + 0.5 - bx, y + 0.5 - 6.5);
      if (d > 2.1) continue;
      g.set(x, y, y < 7 ? hex('#e0403a') : WHITE);
    }
    g.set(bx - 1, 7, INK); g.set(bx, 7, INK); g.set(bx - 1, 5, lighten(hex('#e0403a'), 0.5));
  }
}
