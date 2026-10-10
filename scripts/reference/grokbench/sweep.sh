#!/usr/bin/env bash
# usage: sweep.sh TAG TIMEOUT_S [grok.py args...]   -> logs/TAG.log + one summary line in logs/summary.txt
D=$(cd "$(dirname "$0")" && pwd)
tag=$1; to=$2; shift 2
out=$(python3 "$D/run.py" "$D/logs/$tag.log" "$to" -- "$D/.venv/bin/python" "$D/grok.py" "$@" 2>&1 | grep -E 'event=done|RUN')
done_line=$(echo "$out" | grep done | grep -oE '(steps_run|steps_per_s|final_test_acc|final_train_acc|train99_step|test95_step|test95_s|total_since_launch_s)=[^ ]+' | tr '\n' ' ')
run_line=$(echo "$out" | grep RUN | grep -oE '(rc|first_step_s|cpu_avg%|peak_rss_MB|gpu_util_avg%)=[^ ]+' | tr '\n' ' ')
last=$(grep ' step=' "$D/logs/$tag.log" | tail -1 | grep -oE '(step|test_acc|wall_s)=[^ ]+' | tr '\n' ' ')
echo "$tag | $* | $done_line | $run_line | last: $last" | tee -a "$D/logs/summary.txt"
