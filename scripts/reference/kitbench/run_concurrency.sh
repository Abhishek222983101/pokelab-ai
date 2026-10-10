#!/usr/bin/env bash
# Item 2 driver: grok MLP 1x/2x/3x concurrent, Nanda transformer 1x/2x concurrent (each run capped at 120 s).
# Full METRIC {json} logs -> logs/conc_<tag>_n<N>.log ; summary lines echoed to stdout.
K=$(cd "$(dirname "$0")" && pwd)
S=$(dirname "$K")
PY=${PY:-$S/grokbench/.venv/bin/python}
G=$S/grokbench/grok.py
MLP="--model mlp --device cuda --p 113 --frac 0.3 --lr 3e-3 --wd 1.0 --steps 20000 --stop_at 0.99"
TF="--model transformer --device cuda --frac 0.3 --steps 30000 --stop_at 0.99"
power() {
  printf 'METRIC {"step":"power","tag":"%s","ac_online":%s,"battery_pct":%s,"ppd_profile":"%s","wall_s":0}\n' \
    "$1" "$(cat /sys/class/power_supply/ACAD/online)" "$(cat /sys/class/power_supply/BAT1/capacity)" "$(powerprofilesctl get 2>/dev/null)"
}
run() {  # tag n args...
  local tag=$1 n=$2; shift 2
  local log=$K/logs/conc_${tag}_n${n}.log
  power "${tag}_n${n}" > "$log"
  timeout 260 "$PY" -I "$K/concurrency.py" --n "$n" --cap 120 --tag "$tag" -- "$PY" "$G" "$@" >> "$log" 2>&1
  grep -h -E '"step": "(run_summary|agg_summary)"|"step":"power"' "$log"
  sleep 3
}
for n in 1 2 3; do run mlp $n $MLP; done
for n in 1 2; do run tf $n $TF; done
