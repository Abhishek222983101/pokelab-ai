/**
 * The PokéLab wordmark, drawn from a 5x7 pixel alphabet as one SVG (no image, no font).
 * POKE sits flat; LAB climbs one cell per letter — a learning curve that spells the product.
 * Same bevel / outline / drop-shadow construction as the PokeStonks wordmark, so the family resemblance is exact.
 */

const GLYPHS: Record<string, string[]> = {
  P: ['1111.', '1...1', '1...1', '1111.', '1....', '1....', '1....'],
  O: ['.111.', '1...1', '1...1', '1...1', '1...1', '1...1', '.111.'],
  K: ['1...1', '1..1.', '1.1..', '11...', '1.1..', '1..1.', '1...1'],
  E: ['11111', '1....', '1....', '1111.', '1....', '1....', '11111'],
  L: ['1....', '1....', '1....', '1....', '1....', '1....', '11111'],
  A: ['.111.', '1...1', '1...1', '11111', '1...1', '1...1', '1...1'],
  B: ['1111.', '1...1', '1...1', '1111.', '1...1', '1...1', '1111.'],
};

const WORD = 'POKELAB';
const FLAT = 4; // POKE stays on the baseline
const GAP = 1;
const GW = 5;
const GH = 7;
const S = 2; // sub-cells per glyph cell: bold 2-unit strokes under a 1-unit outline

const COLORS = { shadow: '#0e1c5c', outline: '#183088', gloss: '#fff7c0', top: '#f8d858', bottom: '#d8a830' };

const cellsToPath = (cells: Iterable<string>) => {
  let d = '';
  for (const key of cells) {
    const [x, y] = key.split(',').map(Number);
    d += `M${x} ${y}h1v1h-1z`;
  }
  return d;
};

function dilate(cells: Set<string>): Set<string> {
  const out = new Set<string>();
  for (const key of cells) {
    const [x, y] = key.split(',').map(Number);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) out.add(`${x + dx},${y + dy}`);
  }
  return out;
}

function build() {
  const rise = WORD.length - FLAT;
  const gloss = new Set<string>();
  const top = new Set<string>();
  const bottom = new Set<string>();
  const all = new Set<string>();

  [...WORD].forEach((ch, i) => {
    const lift = i < FLAT ? 0 : i - FLAT + 1;
    const ox = i * (GW + GAP) + 1;
    const oy = rise - lift + 1;
    GLYPHS[ch].forEach((row, r) => {
      [...row].forEach((c, col) => {
        if (c !== '1') return;
        for (let dy = 0; dy < S; dy++) {
          for (let dx = 0; dx < S; dx++) {
            const key = `${(ox + col) * S + dx},${(oy + r) * S + dy}`;
            all.add(key);
            if (r === 0 && dy === 0) gloss.add(key);
            else if (r <= 3) top.add(key);
            else bottom.add(key);
          }
        }
      });
    });
  });

  const outlineZone = dilate(all);
  const outline = new Set([...outlineZone].filter((k) => !all.has(k)));
  const shadowZone = new Set<string>();
  for (const key of outlineZone) {
    const [x, y] = key.split(',').map(Number);
    shadowZone.add(`${x + S},${y + S}`);
  }
  const shadow = new Set([...shadowZone].filter((k) => !outlineZone.has(k)));

  return {
    width: (WORD.length * (GW + GAP) - GAP + 3) * S + S,
    height: (GH + rise + 3) * S + S,
    shadow: cellsToPath(shadow),
    outline: cellsToPath(outline),
    bottom: cellsToPath(bottom),
    top: cellsToPath(top),
    gloss: cellsToPath(gloss),
  };
}

const G = build();

export function Logotype({ className, title = 'PokéLab' }: { className?: string; title?: string }) {
  return (
    <svg
      className={className}
      viewBox={`0 0 ${G.width} ${G.height}`}
      role="img"
      aria-label={title}
      shapeRendering="crispEdges"
      style={{ display: 'block', width: '100%', height: 'auto', overflow: 'visible' }}
    >
      <path d={G.shadow} fill={COLORS.shadow} opacity="0.5" />
      <path d={G.outline} fill={COLORS.outline} />
      <path d={G.bottom} fill={COLORS.bottom} />
      <path d={G.top} fill={COLORS.top} />
      <path d={G.gloss} fill={COLORS.gloss} />
    </svg>
  );
}
