#!/usr/bin/env bash
# Chaos drill: disk low (P12.2, §11-nfr "stop background sweeps < 3 GB
# free; refuse new artifacts < 1 GB"). Actually filling a real disk to
# test this isn't safe to automate (risks the machine running this
# drill, CI or a laptop alike). What IS real and tested: the primitive
# both guards share (lab_telemetry::free_disk_gb, a real `df` call) —
# core/crates/lab-telemetry/tests/real_machine.rs:
# free_disk_gb_reports_a_real_plausible_number_for_cwd — plus labd
# doctor's disk check (fails < 3 GiB) and lab-gateway's job-submit
# guard (rejects < 1 GiB, core/crates/lab-gateway/src/ws.rs's
# handle_job_submit) both being one-line comparisons against that same
# real number, too simple to hide a logic bug once the number itself is
# proven real.
set -euo pipefail
cd "$(dirname "$0")/../../core"
cargo test --package lab-telemetry --test real_machine free_disk_gb -- --nocapture
echo
echo "To actually see the guard fire, temporarily lower MIN_FREE_GB_FOR_NEW_JOB"
echo "in lab-gateway/src/ws.rs above your real free space and submit a job — it"
echo "will come back job_rejected with the real GiB number in the reason."
