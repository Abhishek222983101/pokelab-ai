#!/usr/bin/env bash
# Item 3 driver: teacher once (saved), then student 784-800-800-10 and student 784-30-10 (hard vs KD T in {1,4,20}).
K=$(cd "$(dirname "$0")" && pwd)
S=$(dirname "$K")
PY=${PY:-$S/grokbench/.venv/bin/python}
D=/home/arch-nitro/elevate-ps03/data/raw/mnist
mkdir -p "$K/out"
printf 'METRIC {"step":"power","ac_online":%s,"battery_pct":%s,"ppd_profile":"%s","wall_s":0}\n' \
  "$(cat /sys/class/power_supply/ACAD/online)" "$(cat /sys/class/power_supply/BAT1/capacity)" "$(powerprofilesctl get 2>/dev/null)"
cd /tmp || exit 1
timeout 300 "$PY" -I "$K/kd_mnist.py" --data "$D" --teacher_epochs ${TEP:-10} --student 800,800 --student_epochs ${SEP:-10} \
  --temps 1,4,20 --alpha 0.9 --save_teacher "$K/out/kd_teacher.pt"
timeout 300 "$PY" -I "$K/kd_mnist.py" --data "$D" --load_teacher "$K/out/kd_teacher.pt" --student 30 --student_epochs ${SEP:-10} \
  --temps 1,4,20 --alpha 0.9
