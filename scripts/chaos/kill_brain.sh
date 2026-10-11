#!/usr/bin/env bash
# Chaos drill: kill brain mid-project (P12.2, AC-23's "kill brain mid-
# project -> resumed < 10s with no lost events"). Runs the real Rust
# E2E test that drops the brain connection immediately after it submits
# a job, and proves a real client still sees that job run to real
# completion — labd's job execution does not depend on brain staying
# connected. See core/crates/lab-gateway/tests/chaos_kill_brain_e2e.rs
# for the honest limitation this drill documents: there is no process
# supervisor that auto-restarts a crashed brain with backoff yet.
set -euo pipefail
cd "$(dirname "$0")/../../core"
cargo test --package lab-gateway --test chaos_kill_brain_e2e -- --nocapture
