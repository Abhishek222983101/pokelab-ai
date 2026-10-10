#!/usr/bin/env bash
# The 5 paper PDFs behind the demo's gyms (grokking, distillation, NeRF,
# Matbench, tabular arena).
set -euo pipefail
cd "$(dirname "$0")/.."

n=$(find data/papers -maxdepth 1 -name '*.pdf' 2>/dev/null | wc -l)
if [ "$n" -ge 5 ]; then
  echo "data/papers has $n PDFs"
else
  echo "MISSING paper PDFs (found $n, expected >= 5) — see scripts/reference/papers/"
  exit 1
fi
