#!/usr/bin/env bash
# Item 4 driver.  usage: run_nerf.sh probe            -> 10-iter speed probe for fp32 / tf32 / bf16
#                        run_nerf.sh full PREC ITERS CAP -> L=6 run (ITERS, train-time cap CAP s) then L=0 run to the same iteration
K=$(cd "$(dirname "$0")" && pwd)
S=$(dirname "$K")
PY=${PY:-$S/grokbench/.venv/bin/python}
D=/home/arch-nitro/elevate-ps03/data/raw/tiny_nerf/tiny_nerf_data.npz
mkdir -p "$K/out"
cd /tmp || exit 1
printf 'METRIC {"step":"power","ac_online":%s,"battery_pct":%s,"ppd_profile":"%s","wall_s":0}\n' \
  "$(cat /sys/class/power_supply/ACAD/online)" "$(cat /sys/class/power_supply/BAT1/capacity)" "$(powerprofilesctl get 2>/dev/null)"
if [ "$1" = probe ]; then
  for prec in fp32 tf32 bf16; do
    ch=5000; [ $prec = bf16 ] && ch=10000
    timeout 120 "$PY" -I "$K/tiny_nerf.py" --data "$D" --iters 10 --eval_every 5 --video_frames 3 --precision $prec --chunk $ch
  done
  exit 0
fi
prec=$2; iters=$3; cap=$4
ch=5000; [ "$prec" = bf16 ] && ch=10000
out6=$(timeout $((cap + 240)) "$PY" -I "$K/tiny_nerf.py" --data "$D" --iters "$iters" --L 6 --eval_every 50 --precision "$prec" \
  --chunk $ch --time_cap "$cap" --video_frames 120 --save_frames "$K/out/nerf_L6_spiral_frames.npy")
echo "$out6"
done_iters=$(echo "$out6" | grep '"train_done"' | sed -E 's/.*"iters_done": ([0-9]+).*/\1/')
timeout $((cap + 240)) "$PY" -I "$K/tiny_nerf.py" --data "$D" --iters $((done_iters - 1)) --L 0 --eval_every 50 --precision "$prec" \
  --chunk $ch --time_cap $((cap * 2)) --video_frames 12
