#!/usr/bin/env python3
"""The asset pipeline (P9.1, §9.6). Scoped honestly for this pass:
copies STATIC sprites (gen5 front/back PNGs) for the species the roster
actually uses, plus the two trainer portraits (Ash, Oak), into
web/public/assets/gen/, and writes a manifest.json Phaser loads at boot.

The full spec describes unpacking the ANIMATED Showdown GIFs frame-by-
frame into a packed atlas with per-frame durations (§9.6's table) — real
extra work (GIF decoding + strip packing) that's a genuine follow-on,
not done here. Static sprites are real, licensed the same way, and
load directly into Phaser with zero extra processing — which is why
they're the honest choice for "get something real on screen" now.
"""
from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
SHOWDOWN = ROOT / "assets" / "vendor" / "showdown" / "sprites"
OUT = ROOT / "web" / "public" / "assets" / "gen"

# Eevee is the lore-fixed species for every spawned specialist (§2.4) —
# always included regardless of what's in roster.toml.
ALWAYS_INCLUDE_SPECIES = {"eevee"}
TRAINERS = {"ash": "ash.png", "oak": "oak.png"}


def roster_species() -> set[str]:
    roster_path = ROOT / "config" / "roster.toml"
    with open(roster_path, "rb") as f:
        data = tomllib.load(f)
    species = {a["species"] for a in data.get("agent", [])}
    # "oak" in roster.toml is the meta-controller's species name, but his
    # sprite is a TRAINER portrait, not a Pokémon — handled via TRAINERS,
    # not the mon pipeline, so exclude it here.
    return (species | ALWAYS_INCLUDE_SPECIES) - set(TRAINERS)


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mons").mkdir(exist_ok=True)
    (OUT / "trainers").mkdir(exist_ok=True)

    manifest: dict = {"mons": {}, "trainers": {}}

    missing: list[str] = []
    for species in sorted(roster_species()):
        front_src = SHOWDOWN / "gen5" / f"{species}.png"
        back_src = SHOWDOWN / "gen5-back" / f"{species}.png"
        if not front_src.exists() or not back_src.exists():
            missing.append(species)
            continue
        shutil.copy(front_src, OUT / "mons" / f"{species}_front.png")
        shutil.copy(back_src, OUT / "mons" / f"{species}_back.png")
        manifest["mons"][species] = {
            "front": f"assets/gen/mons/{species}_front.png",
            "back": f"assets/gen/mons/{species}_back.png",
        }

    for name, filename in TRAINERS.items():
        src = SHOWDOWN / "trainers" / filename
        if not src.exists():
            missing.append(f"trainer:{name}")
            continue
        shutil.copy(src, OUT / "trainers" / filename)
        manifest["trainers"][name] = f"assets/gen/trainers/{filename}"

    if missing:
        manifest["missing"] = missing

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps(result, indent=2))
