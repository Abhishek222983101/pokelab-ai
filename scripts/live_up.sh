#!/bin/bash
# One command for the demo: (re)starts labd + the brain against var/lab.db and prints the links.
# Usage: bash scripts/live_up.sh        (add --build to rebuild the website first)
cd "$(dirname "$0")/.."
[ "$1" = "--build" ] && (cd web && npx next build >/dev/null 2>&1 && echo "web built")
pkill -x labd 2>/dev/null; pkill -f "[p]okelab_brain.main" 2>/dev/null; sleep 1
set -a; source .env; set +a
export LABD_WORKERS_PYTHON=$PWD/workers/.venv/bin/python LABD_WORKERS_CWD=$PWD/workers LABD_WORKER_DEVICE=cuda \
  LABD_POOL_SIZE=2 LABD_DB_PATH=$PWD/var/lab.db LABD_PORT=7700 LABD_WEB_DIR=$PWD/web/out
nohup ./core/target/debug/labd up > /tmp/labd_live.log 2>&1 &
for i in $(seq 1 20); do curl -sf localhost:7700/api/health >/dev/null && break; sleep 1; done
LABD_HOST=127.0.0.1 nohup ./brain/.venv/bin/python -m pokelab_brain.main > /tmp/brain_live.log 2>&1 &
sleep 4
curl -sf localhost:7700/api/health >/dev/null && echo "labd OK" || echo "labd FAILED: see /tmp/labd_live.log"
grep -q "brain connected" /tmp/brain_live.log && echo "brain OK" || echo "brain FAILED: see /tmp/brain_live.log"
echo "LAB DESK : http://localhost:7700/lab/"
echo "TITLE    : http://localhost:7700/"
echo "PUBLIC   : $(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel.log | tail -1)"
