#!/usr/bin/env bash
# MNIST, tiny_nerf, Matbench (expt_gap, steels) and the tabular arena sets.
set -euo pipefail
cd "$(dirname "$0")/.."

for d in mnist tiny_nerf matbench_expt_gap matbench_steels tabular; do
  if [ -d "data/raw/$d" ] && [ -n "$(ls -A "data/raw/$d" 2>/dev/null)" ]; then
    echo "data/raw/$d present"
  else
    echo "MISSING data/raw/$d — re-run scripts/reference/kitbench/fetch_all.sh"
    exit 1
  fi
done
