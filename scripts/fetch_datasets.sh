#!/usr/bin/env bash
# Pre-warms the real datasets the P11 kits use, so a demo's first run of
# each kit isn't paying a download mid-reproduction. Not required —
# every kit self-fetches on its own first real run (workers/pokelab_workers/
# kits/data_home.py) — this just does it up front, once, on purpose.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="workers/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "workers/.venv not found — run 'uv sync' in workers/ first" >&2
  exit 1
fi

"$PY" -c "
from pokelab_workers.kits.materials.data import load_split
from pokelab_workers.kits.arena.data import load_dataset
from pokelab_workers.kits.nerf.data import load_tiny_nerf_data

print('fetching materials (superconductor, OpenML 44148)...')
load_split(seed=0)
print('fetching arena/magictelescope (OpenML 1120)...')
load_dataset('magictelescope')
print('fetching arena/electricity (OpenML 151)...')
load_dataset('electricity')
print('fetching nerf (tiny_nerf lego dataset)...')
load_tiny_nerf_data()
print('fetching distillation (MNIST, OpenML 554) via the same OpenML client...')
from sklearn.datasets import fetch_openml
from pokelab_workers.kits.data_home import ensure_data_home
fetch_openml(data_id=554, as_frame=False, parser='liac-arff', data_home=ensure_data_home())
print('all P11 datasets cached under workers/var/data/')
"
