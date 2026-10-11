#!/usr/bin/env python3
"""The asset pipeline (§9.6). Single entry point:  python3 assets/build_atlases.py

Reads the pre-downloaded sources in assets/vendor/ (see scripts/fetch_assets.sh
and scripts/fetch_sprites.py) and writes everything the game loads into
web/public/assets/gen/ (gitignored, fully regenerated each run):

  battle/<name>_{front,back}.png/.json   Showdown Gen 5 animated GIFs, unpacked
                                         (Pillow composites partial frames with
                                         their disposal), trimmed to one common
                                         bbox, packed, Phaser 3 JSON-Hash atlas
                                         with per-frame `duration` (ms).
  battle/<name>_{front,back}_static.png  Gen 5 static fallback / "classic" toggle.
  walk/<name>.png/.json                  PMD SpriteCollab Walk/Idle/Sleep/Attack/Hurt,
                                         rows Down/Right/Up/Left only, keys
                                         <anim>_<dir>_<i>, `duration` in ms.
  people/<name>.png/.json                FireRed overworld walkers (pret), RGBA,
                                         keys <dir>_<pose>, right_* pre-flipped.
  trainers/<name>.png                    Showdown trainer portraits.
  cries/<dex>.ogg                        PokeAPI cries.
  manifest.json, CREDITS.md

Every atlas JSON also carries a top-level "anims" helper
({"walk_down": {"frames": [...keys], "durations": [...ms]}}); Phaser copies
unknown top-level keys into texture.customData, and each frame's own JSON
(incl. `duration`) lands in frame.customData.

Frame rects are packed into rows wrapped at MAX_W (2048 px) rather than one
unbounded strip, so no texture exceeds WebGL's commonly-safe 4096 limit
(Charizard's back GIF alone is 49 x 146 px wide). Consumers must read
rects from the JSON, never assume a strip layout.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "assets" / "vendor"
SHOWDOWN = VENDOR / "showdown" / "sprites"
PMD_DIR = VENDOR / "pmd"
FRLG_DIR = VENDOR / "frlg"
CRIES_DIR = VENDOR / "cries"
PUBLIC = ROOT / "web" / "public"
OUT = PUBLIC / "assets" / "gen"
URL_PREFIX = "assets/gen"

MAX_W = 2048
PAD = 1  # transparent gutter between frames (avoids bleeding when zoomed)

# species list + FireRed people map live in the fetch script (one source of truth)
_spec = importlib.util.spec_from_file_location(
    "fetch_sprites", ROOT / "scripts" / "fetch_sprites.py")
_fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fetch)
DEX: dict[str, int] = _fetch.DEX
FRLG_PEOPLE: dict[str, str] = _fetch.FRLG_PEOPLE

# game name -> Showdown trainers/ filename (classic/base variants).
# Showdown has no Nurse Joy portrait; `nurse.png` is the Gen 5 Nurse class.
TRAINERS: dict[str, str] = {
    "ash": "ash.png", "oak": "oak.png", "nursejoy": "nurse.png", "bill": "bill.png",
    "sabrina": "sabrina.png", "ltsurge": "ltsurge.png", "blaine": "blaine.png",
    "brock": "brock.png", "erika": "erika.png",
}

PMD_ANIMS = ["Walk", "Idle", "Sleep", "Attack", "Hurt"]
# PMD 8-direction row order; we keep the 4 grid-engine directions.
PMD_ROWS = {"down": 0, "right": 2, "up": 4, "left": 6}

# FireRed/LeafGreen object-event strip (16x32 frames), determined by
# inspecting the pret PNGs:
#   0 down idle | 1 up idle | 2 left idle | 3,4 down walk | 5,6 up walk | 7,8 left walk
# NPCs that never walk in FRLG (gym leaders) ship only frames 0-2; Nurse Joy
# ships 0-2 + a bow (frame 3). Missing walk poses alias the idle rect.
FRLG_FRAME_W, FRLG_FRAME_H = 16, 32
FRLG_ORDER = ["down_idle", "up_idle", "left_idle",
              "down_walk1", "down_walk2", "up_walk1", "up_walk2",
              "left_walk1", "left_walk2"]
FRLG_EXTRA = {"nursejoy": ["down_bow"]}


def url(p: Path) -> str:
    return p.relative_to(PUBLIC).as_posix()


# --------------------------------------------------------------------- packing
def pack(frames: list[tuple[str, Image.Image]], aliases: dict[str, str] | None = None
         ) -> tuple[Image.Image, dict[str, dict]]:
    """Shelf-pack (key, RGBA image) into rows no wider than MAX_W.
    Frames with the same image object are stored once. Returns the sheet and
    {key: {"x","y","w","h"}}; `aliases` maps extra keys onto existing keys."""
    rects: dict[str, dict] = {}
    placed: dict[int, dict] = {}
    x = y = shelf_h = sheet_w = 0
    for key, im in frames:
        if id(im) in placed:
            rects[key] = placed[id(im)]
            continue
        w, h = im.size
        if x and x + w > MAX_W:
            x, y, shelf_h = 0, y + shelf_h + PAD, 0
        r = {"x": x, "y": y, "w": w, "h": h, "_im": im}
        rects[key] = placed[id(im)] = r
        x += w + PAD
        shelf_h = max(shelf_h, h)
        sheet_w = max(sheet_w, x - PAD)
    sheet = Image.new("RGBA", (max(sheet_w, 1), max(y + shelf_h, 1)), (0, 0, 0, 0))
    for r in placed.values():
        sheet.paste(r.pop("_im"), (r["x"], r["y"]))
    for alias, target in (aliases or {}).items():
        rects[alias] = rects[target]
    return sheet, rects


def atlas_json(image_name: str, sheet: Image.Image, order: list[str],
               rects: dict[str, dict], durations: dict[str, int],
               anims: dict[str, list[str]], extra_meta: dict | None = None) -> dict:
    frames = {}
    for key in order:
        r = rects[key]
        frames[key] = {
            "frame": {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": r["w"], "h": r["h"]},
            "sourceSize": {"w": r["w"], "h": r["h"]},
            "duration": int(durations.get(key, 100)),
        }
    meta = {"app": "pokelab assets/build_atlases.py", "version": "1",
            "image": image_name, "format": "RGBA8888",
            "size": {"w": sheet.width, "h": sheet.height}, "scale": "1"}
    if extra_meta:
        meta.update(extra_meta)
    return {
        "frames": frames,
        "anims": {name: {"frames": keys, "durations": [frames[k]["duration"] for k in keys]}
                  for name, keys in anims.items()},
        "meta": meta,
    }


def save(sheet: Image.Image, atlas: dict, png: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(png, optimize=True)
    png.with_suffix(".json").write_text(json.dumps(atlas, separators=(",", ":")))


# ---------------------------------------------------------------------- battle
def gif_frames(path: Path) -> list[tuple[Image.Image, int]]:
    """Full-canvas RGBA frames + ms durations. Pillow's GIF reader composites
    each partial frame onto the running canvas honouring the previous frame's
    disposal method (0/1 keep, 2 restore-to-transparent, 3 restore-previous),
    so every yielded frame is the complete picture. Durations <= 10 ms (or
    missing) become 100 ms, matching how browsers play the GIF on Showdown."""
    out = []
    with Image.open(path) as im:
        for fr in ImageSequence.Iterator(im):
            d = fr.info.get("duration")
            d = 100 if not d or d <= 10 else int(d)
            out.append((fr.convert("RGBA").copy(), d))
    return out


def build_battle(name: str, side: str, missing: list[str]) -> dict | None:
    ani_dir, static_dir = ("ani", "gen5") if side == "front" else ("ani-back", "gen5-back")
    gif = SHOWDOWN / ani_dir / f"{name}.gif"
    static = SHOWDOWN / static_dir / f"{name}.png"
    base = OUT / "battle" / f"{name}_{side}"
    entry: dict = {}

    if static.exists():
        sp = base.parent / f"{name}_{side}_static.png"
        sp.parent.mkdir(parents=True, exist_ok=True)
        Image.open(static).convert("RGBA").save(sp, optimize=True)
        entry["static"] = url(sp)

    if gif.exists():
        frames = gif_frames(gif)
        source = "ani"
    elif static.exists():
        frames = [(Image.open(static).convert("RGBA"), 100)]
        source = "gen5-static"
        missing.append(f"battle:{name}:{side}:gif (using gen5 static)")
    else:
        missing.append(f"battle:{name}:{side}")
        return entry or None

    src_w, src_h = frames[0][0].size
    bbox = None
    for im, _ in frames:
        b = im.getchannel("A").getbbox()
        if b:
            bbox = b if bbox is None else (min(bbox[0], b[0]), min(bbox[1], b[1]),
                                           max(bbox[2], b[2]), max(bbox[3], b[3]))
    bbox = bbox or (0, 0, src_w, src_h)
    prefix = f"{name}_{side}"
    keyed = [(f"{prefix}_{i}", im.crop(bbox)) for i, (im, _) in enumerate(frames)]
    durations = {f"{prefix}_{i}": d for i, (_, d) in enumerate(frames)}
    sheet, rects = pack(keyed)
    order = [k for k, _ in keyed]
    atlas = atlas_json(base.name + ".png", sheet, order, rects, durations, {prefix: order},
                       {"source": source,
                        # where the trimmed frame sat in the original GIF canvas
                        "trim": {"x": bbox[0], "y": bbox[1],
                                 "sourceW": src_w, "sourceH": src_h}})
    save(sheet, atlas, base.with_suffix(".png"))
    entry.update({"png": url(base.with_suffix(".png")), "json": url(base.with_suffix(".json")),
                  "frames": len(order), "w": bbox[2] - bbox[0], "h": bbox[3] - bbox[1]})
    return entry


# ------------------------------------------------------------------------ walk
def parse_anim_data(xml_path: Path) -> tuple[int | None, dict[str, dict]]:
    root = ET.parse(xml_path).getroot()
    shadow = root.findtext("ShadowSize")
    by_name = {a.findtext("Name"): a for a in root.iter("Anim")}

    def resolve(name: str) -> ET.Element | None:
        seen = set()
        while name in by_name and by_name[name].findtext("CopyOf") and name not in seen:
            seen.add(name)
            name = by_name[name].findtext("CopyOf")
        return by_name.get(name)

    anims = {}
    for want in PMD_ANIMS:
        a = resolve(want)
        if a is None:
            continue
        anims[want] = {
            "src": a.findtext("Name"),
            "fw": int(a.findtext("FrameWidth")),
            "fh": int(a.findtext("FrameHeight")),
            "ticks": [int(d.text) for d in a.find("Durations").iter("Duration")],
        }
    return (int(shadow) if shadow is not None else None), anims


def build_walk(name: str, dex: int, missing: list[str]) -> dict | None:
    sdir = PMD_DIR / f"{dex:04d}"
    xml = sdir / "AnimData.xml"
    if not xml.exists():
        missing.append(f"walk:{name}")
        return None
    shadow, anims = parse_anim_data(xml)
    frames: list[tuple[str, Image.Image]] = []
    durations: dict[str, int] = {}
    aliases: dict[str, str] = {}
    anim_keys: dict[str, list[str]] = {}
    info: dict[str, dict] = {}
    for want in PMD_ANIMS:
        a = anims.get(want)
        sheet_path = sdir / f"{a['src']}-Anim.png" if a else None
        if not a or not sheet_path.exists():
            missing.append(f"walk:{name}:{want.lower()}")
            continue
        sheet = Image.open(sheet_path).convert("RGBA")
        fw, fh, ticks = a["fw"], a["fh"], a["ticks"]
        cols, rows = sheet.width // fw, sheet.height // fh
        n = min(len(ticks), cols)
        if n != len(ticks) or rows not in (1, 8):
            print(f"  warn: {name} {want}: sheet {sheet.size} vs {fw}x{fh}x{len(ticks)} "
                  f"({rows} rows)", file=sys.stderr)
        lname = want.lower()
        for d, row in PMD_ROWS.items():
            keys = [f"{lname}_{d}_{i}" for i in range(n)]
            anim_keys[f"{lname}_{d}"] = keys
            for i, k in enumerate(keys):
                durations[k] = round(ticks[i] * 1000 / 60)
                if rows == 1 and d != "down":
                    aliases[k] = f"{lname}_down_{i}"  # single-row anim: same art all dirs
                    continue
                r = row if rows == 8 else 0
                frames.append((k, sheet.crop((i * fw, r * fh, (i + 1) * fw, (r + 1) * fh))))
        info[lname] = {"frameW": fw, "frameH": fh, "frames": n, "rows": rows}

    if "walk" not in info:
        missing.append(f"walk:{name}")
        return None
    sheet, rects = pack(frames, aliases)
    order = [k for keys in anim_keys.values() for k in keys]
    png = OUT / "walk" / f"{name}.png"
    atlas = atlas_json(png.name, sheet, order, rects, durations, anim_keys,
                       {"shadowSize": shadow, "anims": info,
                        "anchor": "frame centre = PMD sprite origin"})
    save(sheet, atlas, png)
    return {"png": url(png), "json": url(png.with_suffix(".json")),
            "anims": info, "shadowSize": shadow}


# ---------------------------------------------------------------------- people
def frlg_rgba(path: Path) -> Image.Image:
    """Indexed FRLG PNG -> RGBA with palette index 0 fully transparent."""
    im = Image.open(path)
    if im.mode != "P":
        raise ValueError(f"{path} is {im.mode}, expected indexed")
    idx = im.copy()
    rgba = im.convert("RGB").convert("RGBA")
    alpha = idx.point(lambda v: 0 if v == 0 else 255, mode="L")
    rgba.putalpha(alpha)
    return rgba


def build_people(name: str, fname: str, missing: list[str]) -> dict | None:
    src = FRLG_DIR / fname
    if not src.exists():
        missing.append(f"people:{name}")
        return None
    strip = frlg_rgba(src)
    n = strip.width // FRLG_FRAME_W
    raw = [strip.crop((i * FRLG_FRAME_W, 0, (i + 1) * FRLG_FRAME_W, FRLG_FRAME_H))
           for i in range(n)]
    walks = n >= 9
    poses = dict(zip(FRLG_ORDER, raw[:9] if walks else raw[:3]))
    extras = dict(zip(FRLG_EXTRA.get(name, []), raw[9:] if walks else raw[3:]))
    aliases: dict[str, str] = {}
    if not walks:
        for d in ("down", "up", "left"):
            for p in ("walk1", "walk2"):
                aliases[f"{d}_{p}"] = f"{d}_idle"
    frames = list(poses.items()) + list(extras.items())
    # right = mirrored left, baked in so the game never flips at runtime
    for p in ("idle", "walk1", "walk2"):
        if f"left_{p}" in poses:
            frames.append((f"right_{p}", ImageOps.mirror(poses[f"left_{p}"])))
        else:
            aliases[f"right_{p}"] = "right_idle"
    sheet, rects = pack(frames, aliases)
    order = [f"{d}_{p}" for d in ("down", "up", "left", "right")
             for p in ("idle", "walk1", "walk2")] + list(extras)
    # FRLG walk cycle: walk1, idle, walk2, idle (each step ~ 8 frames @60fps)
    durations = {k: 133 for k in order}
    anims = {f"walk_{d}": [f"{d}_walk1", f"{d}_idle", f"{d}_walk2", f"{d}_idle"]
             for d in ("down", "up", "left", "right")}
    anims.update({f"idle_{d}": [f"{d}_idle"] for d in ("down", "up", "left", "right")})
    png = OUT / "people" / f"{name}.png"
    atlas = atlas_json(png.name, sheet, order, rects, durations, anims,
                       {"source": f"pret/pokefirered people/{fname}", "walks": walks})
    save(sheet, atlas, png)
    return {"png": url(png), "json": url(png.with_suffix(".json")),
            "frameW": FRLG_FRAME_W, "frameH": FRLG_FRAME_H, "walks": walks,
            "poses": order}


# --------------------------------------------------------------------- credits
def write_credits(species_dex: dict[str, int]) -> None:
    names: dict[str, str] = {}
    cn = PMD_DIR / "credit_names.txt"
    if cn.exists():
        for line in cn.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if parts and parts[0]:
                contact = parts[2].strip() if len(parts) > 2 else ""
                label = parts[0] + (f" ({contact})" if contact.startswith("http") else "")
                names[parts[0]] = label
                # credits.txt usually cites authors by Discord id (<@!123>)
                if len(parts) > 1 and parts[1].strip():
                    names[parts[1].strip()] = label
                    names[parts[1].strip().replace("<@!", "<@")] = label
    lines = ["# Asset credits", "",
             "Generated by `assets/build_atlases.py`. All Pokémon characters and art are",
             "© Nintendo / Creatures Inc. / GAME FREAK inc.; used here non-commercially",
             "for a hackathon demo.", "",
             "## Sources", "",
             "- **Battle sprites & trainer portraits** — Pokémon Showdown "
             "(play.pokemonshowdown.com/sprites; Gen 5 animated `ani/`, `ani-back/`, "
             "`gen5/`, `trainers/`). Credit to the Showdown sprite artists and "
             "the Smogon sprite project; portraits are not edited.",
             "- **Overworld walkers** — pret/pokefirered decompilation "
             "(github.com/pret/pokefirered, `graphics/object_events/pics/people/`), "
             "original art from Pokémon FireRed/LeafGreen (GAME FREAK).",
             "- **Cries** — PokeAPI/cries (github.com/PokeAPI/cries, `cries/pokemon/latest/`).",
             "- **Walking / overworld Pokémon** — PMD SpriteCollab "
             "(github.com/PMDCollab/SpriteCollab, sprites.pmdcollab.org), "
             "per-species authors below.", "",
             "## PMD SpriteCollab authors per species", ""]
    for name, dex in sorted(species_dex.items(), key=lambda kv: kv[1]):
        cf = PMD_DIR / f"{dex:04d}" / "credits.txt"
        authors: list[str] = []
        if cf.exists():
            for line in cf.read_text(encoding="utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) > 1 and parts[1] and parts[1] not in authors:
                    authors.append(parts[1])
        who = ", ".join(names.get(a, a) for a in authors) or "unknown"
        lines.append(f"- {name.capitalize()} (#{dex:04d}): {who}")
    (OUT / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------ main
def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    for sub in ("battle", "walk", "people", "trainers", "cries", "mons"):
        shutil.rmtree(OUT / sub, ignore_errors=True)

    missing: list[str] = []
    manifest: dict = {"battle": {}, "walk": {}, "people": {}, "trainers": {},
                      "cries": {}, "dex": dict(DEX), "mons": {}, "missing": missing}

    for name, dex in DEX.items():
        sides = {s: build_battle(name, s, missing) for s in ("front", "back")}
        sides = {s: e for s, e in sides.items() if e}
        if sides:
            manifest["battle"][name] = sides
        # legacy key used by the pre-rebuild game: static front/back PNGs
        if all("static" in sides.get(s, {}) for s in ("front", "back")):
            manifest["mons"][name] = {s: sides[s]["static"] for s in ("front", "back")}

        w = build_walk(name, dex, missing)
        if w:
            manifest["walk"][name] = w

        cry = CRIES_DIR / f"{dex}.ogg"
        if cry.exists():
            dst = OUT / "cries" / f"{dex}.ogg"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cry, dst)
            manifest["cries"][name] = url(dst)
        else:
            missing.append(f"cry:{name}")

    for name, fname in FRLG_PEOPLE.items():
        p = build_people(name, fname, missing)
        if p:
            manifest["people"][name] = p

    for name, fname in TRAINERS.items():
        src = SHOWDOWN / "trainers" / fname
        if not src.exists():
            missing.append(f"trainer:{name}")
            continue
        dst = OUT / "trainers" / f"{name}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("RGBA").save(dst, optimize=True)
        manifest["trainers"][name] = url(dst)

    write_credits(DEX)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


if __name__ == "__main__":
    m = build()
    print(f"battle:   {len(m['battle'])} species "
          f"({sum(1 for v in m['battle'].values() if 'png' in v.get('front', {}))} front, "
          f"{sum(1 for v in m['battle'].values() if 'png' in v.get('back', {}))} back atlases)")
    print(f"walk:     {len(m['walk'])} species")
    print(f"people:   {len(m['people'])} ({', '.join(m['people'])})")
    print(f"trainers: {len(m['trainers'])} ({', '.join(m['trainers'])})")
    print(f"cries:    {len(m['cries'])}")
    print(f"missing:  {m['missing'] or 'none'}")
    print(f"total size of {OUT.relative_to(ROOT)}: {_size(OUT) / 1e6:.2f} MB")
