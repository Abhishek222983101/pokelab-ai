#!/usr/bin/env bash
# Pushes offline W&B runs (written by workers under var/wandb/) to wandb.ai.
# This is the ONLY place WANDB_API_KEY is read from .env — workers never see
# it (§11.4/§11.6: offline-first, labd syncs separately when online).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "no .env — nothing to sync with" >&2
  exit 1
fi
export WANDB_API_KEY="$(grep -m1 '^WANDB_API_KEY=' .env | cut -d= -f2-)"
if [ -z "${WANDB_API_KEY:-}" ]; then
  echo "WANDB_API_KEY not set in .env — skipping sync (offline runs are kept, nothing is lost)" >&2
  exit 0
fi
if [ ! -d var/wandb ] || [ -z "$(ls -A var/wandb 2>/dev/null)" ]; then
  echo "var/wandb/ is empty — nothing to sync yet"
  exit 0
fi

"${WORKERS_PYTHON:-workers/.venv/bin/python}" -m wandb sync var/wandb/wandb/offline-run-*
