#!/usr/bin/env python3
"""Download the non-Showdown sprite/sound sources for the asset pipeline (§9.6).

Fetches into assets/vendor/ (gitignored):
  pmd/<dex4>/   PMD SpriteCollab AnimData.xml + {Walk,Idle,Sleep,Attack,Hurt}-Anim.png
                (resolving <CopyOf>) + credits.txt; pmd/credit_names.txt
  frlg/         pret/pokefirered overworld people PNGs (indexed, raw)
  cries/        PokeAPI cries <dex>.ogg

Idempotent: a file already on disk (non-empty) is never re-downloaded.
A 404 / network error on one file is reported and the run continues;
the exit code is 1 only if something required is still missing.

Run:  python3 scripts/fetch_sprites.py
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "assets" / "vendor"
PMD_DIR = VENDOR / "pmd"
FRLG_DIR = VENDOR / "frlg"
CRIES_DIR = VENDOR / "cries"

PMD_BASE = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master"
FRLG_BASE = ("https://raw.githubusercontent.com/pret/pokefirered/master/"
             "graphics/object_events/pics/people")
CRIES_BASE = "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest"

# §2.4 roster + Eevee forms + gym aces. Single source of truth for the
# species list — assets/build_atlases.py imports this.
DEX: dict[str, int] = {
    "pichu": 172, "pikachu": 25, "raichu": 26,
    "charmander": 4, "charmeleon": 5, "charizard": 6,
    "bulbasaur": 1, "ivysaur": 2, "venusaur": 3,
    "squirtle": 7, "wartortle": 8, "blastoise": 9,
    "abra": 63, "kadabra": 64, "alakazam": 65,
    "porygon": 137, "porygon2": 233,
    "magnemite": 81, "magneton": 82,
    "hoothoot": 163, "noctowl": 164,
    "zubat": 41, "golbat": 42, "crobat": 169,
    "eevee": 133, "espeon": 196, "jolteon": 135, "flareon": 136,
    "vaporeon": 134, "umbreon": 197,
    # gym aces (Sabrina=alakazam and Surge=raichu are already above)
    "onix": 95, "arcanine": 59, "vileplume": 45,
}

PMD_ANIMS = ["Walk", "Idle", "Sleep", "Attack", "Hurt"]

# game name -> pret filename (graphics/object_events/pics/people/)
FRLG_PEOPLE: dict[str, str] = {
    "red": "red_normal.png",
    "oak": "prof_oak.png",
    "nursejoy": "nurse.png",
    "brock": "brock.png",
    "erika": "erika.png",
    "ltsurge": "lt_surge.png",
    "sabrina": "sabrina.png",
    "blaine": "blaine.png",
    "bill": "bill.png",
}

UA = "pokelab-asset-fetch/1.0 (+offline demo build)"


class Fetcher:
    def __init__(self) -> None:
        self.downloaded = 0
        self.skipped = 0
        self.errors: list[str] = []

    def get(self, url: str, dest: Path, required: bool = True) -> bool:
        """Download url -> dest unless dest already exists. Returns True if
        dest exists afterwards. Never raises on HTTP/network errors."""
        if dest.exists() and dest.stat().st_size > 0:
            self.skipped += 1
            return True
        dest.parent.mkdir(parents=True, exist_ok=True)
        last_err = ""
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(data)
                tmp.replace(dest)
                self.downloaded += 1
                return True
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                if e.code == 404:
                    break  # no point retrying
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.0 * (attempt + 1))
        msg = f"{'MISSING' if required else 'absent (optional)'}: {url} ({last_err})"
        print("  " + msg, file=sys.stderr)
        if required:
            self.errors.append(msg)
        return False


def resolve_pmd_anims(xml_path: Path) -> dict[str, str]:
    """Map each wanted anim name -> the anim whose PNG actually holds the
    pixels (following <CopyOf> chains). Anims absent from the XML are
    omitted."""
    root = ET.parse(xml_path).getroot()
    by_name = {}
    for a in root.iter("Anim"):
        name = a.findtext("Name")
        if name:
            by_name[name] = a
    out: dict[str, str] = {}
    for want in PMD_ANIMS:
        cur, seen = want, set()
        while cur in by_name and by_name[cur].findtext("CopyOf") and cur not in seen:
            seen.add(cur)
            cur = by_name[cur].findtext("CopyOf")
        if cur in by_name:
            out[want] = cur
    return out


def fetch_pmd(f: Fetcher) -> None:
    print("PMD SpriteCollab walking sprites")
    f.get(f"{PMD_BASE}/credit_names.txt", PMD_DIR / "credit_names.txt", required=False)
    for name, dex in DEX.items():
        d4 = f"{dex:04d}"
        sdir = PMD_DIR / d4
        if not f.get(f"{PMD_BASE}/sprite/{d4}/AnimData.xml", sdir / "AnimData.xml"):
            continue
        f.get(f"{PMD_BASE}/sprite/{d4}/credits.txt", sdir / "credits.txt", required=False)
        try:
            resolved = resolve_pmd_anims(sdir / "AnimData.xml")
        except ET.ParseError as e:
            f.errors.append(f"bad AnimData.xml for {name}: {e}")
            (sdir / "AnimData.xml").unlink(missing_ok=True)
            continue
        for want in PMD_ANIMS:
            if want not in resolved:
                print(f"  note: {name} ({d4}) has no {want} anim", file=sys.stderr)
                continue
        for src in sorted(set(resolved.values())):
            f.get(f"{PMD_BASE}/sprite/{d4}/{src}-Anim.png", sdir / f"{src}-Anim.png",
                  required=(src == resolved.get("Walk")))


def fetch_frlg(f: Fetcher) -> None:
    print("pret/pokefirered overworld people")
    for fname in sorted(set(FRLG_PEOPLE.values())):
        f.get(f"{FRLG_BASE}/{fname}", FRLG_DIR / fname)


def fetch_cries(f: Fetcher) -> None:
    print("PokeAPI cries")
    for dex in sorted(set(DEX.values())):
        f.get(f"{CRIES_BASE}/{dex}.ogg", CRIES_DIR / f"{dex}.ogg")


def main() -> int:
    f = Fetcher()
    fetch_pmd(f)
    fetch_frlg(f)
    fetch_cries(f)
    print(f"done: {f.downloaded} downloaded, {f.skipped} already present, "
          f"{len(f.errors)} missing")
    for e in f.errors:
        print("  " + e)
    return 1 if f.errors else 0


if __name__ == "__main__":
    sys.exit(main())
