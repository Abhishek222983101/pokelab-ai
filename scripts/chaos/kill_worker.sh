#!/usr/bin/env bash
# Chaos drill: kill a worker process mid-run (P12.2, AC-23's "kill a
# worker mid-run -> Medic path"). Runs the real Rust test that SIGKILLs
# a live Python worker while a job is running on it and proves the
# caller gets a real Done{status:"error"} instead of hanging forever.
# See core/crates/lab-jobs/tests/chaos_kill_worker.rs for the bug this
# test caught (and the fix in lab-jobs/src/lib.rs).
set -euo pipefail
cd "$(dirname "$0")/../../core"
cargo test --package lab-jobs --test chaos_kill_worker -- --nocapture
