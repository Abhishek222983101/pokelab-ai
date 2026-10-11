#!/usr/bin/env bash
# Sprites, cries and trainer art. Showdown (battle sprites + trainer portraits)
# is pre-mirrored; PMD walkers, FireRed people and cries come from
# scripts/fetch_sprites.py. Everything is pre-downloaded already for this demo
# (campus Wi-Fi blocks pokemonshowdown.com — see docs §11.3); this script
# documents and re-verifies the layout, and is what `just fetch` runs on a
# fresh machine with a working connection.
set -euo pipefail
cd "$(dirname "$0")/.."

DEST=assets/vendor/showdown
if [ -d "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  echo "assets/vendor/showdown already present ($(du -sh "$DEST" | cut -f1)), skipping download"
else
  echo "assets/vendor/showdown missing — see scripts/reference/tools/dl_showdown.py" \
       "(requires a connection that isn't behind a Games-category block)"
  exit 1
fi

# PMD walking sprites, FireRed overworld people, PokeAPI cries
# (raw.githubusercontent.com; idempotent — skips files already on disk)
python3 scripts/fetch_sprites.py
