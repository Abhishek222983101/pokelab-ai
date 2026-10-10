#!/usr/bin/env bash
# AC re-check: NeRF L=0 with seed 1 (300 iters), MLP concurrency 1x/2x/3x, startup bench (N=3)
cd /tmp
pw() { printf 'METRIC {"step":"power","tag":"%s","ac_online":%s,"battery_pct":%s,"ppd_profile":"%s","wall_s":0}\n' "$1" "$(cat /sys/class/power_supply/ACAD/online)" "$(cat /sys/class/power_supply/BAT1/capacity)" "$(powerprofilesctl get)"; }
pw nerf_L0_seed1 > /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/nerf_L0_seed1.log
timeout 200 /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/grokbench/.venv/bin/python -I /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/tiny_nerf.py --data /home/arch-nitro/elevate-ps03/data/raw/tiny_nerf/tiny_nerf_data.npz --iters 300 --L 0 --seed 1 --eval_every 50 --precision bf16 --chunk 10000 --video_frames 3 >> /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/nerf_L0_seed1.log 2>&1
for n in 1 2 3; do
  pw mlpac_n$n > /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/conc_mlpac_n$n.log
  timeout 200 /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/grokbench/.venv/bin/python -I /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/concurrency.py --n $n --cap 120 --tag mlpac -- /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/grokbench/.venv/bin/python /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/grokbench/grok.py --model mlp --device cuda --p 113 --frac 0.3 --lr 3e-3 --wd 1.0 --steps 20000 --stop_at 0.99 >> /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/conc_mlpac_n$n.log 2>&1
  sleep 2
done
pw startup_ac > /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/startup_ac.log
timeout 200 /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/grokbench/.venv/bin/python -I /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/startup_bench.py /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/grokbench/.venv/bin/python 3 >> /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/startup_ac.log 2>&1
echo ac_done >> /tmp/claude-1000/-home-arch-nitro/38d94e90-dde1-4464-b69e-5b8451e21528/scratchpad/kitbench/logs/startup_ac.log
