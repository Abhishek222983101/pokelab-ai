#!/usr/bin/env bash
# Chaos drill: unplug charger (P12.2). Can't be automated (it's a
# physical action) — this is the manual rehearsal step: unplug the
# charger, then run `labd doctor` and confirm the real "power" check
# (core/crates/labd/src/doctor.rs's check_power, backed by the real
# lab_telemetry::sample_power/should_warn_power — already tested in
# core/crates/lab-telemetry/tests/real_machine.rs) flips from ✅ to ❌
# with the "plug in + performance mode" warning.
set -euo pipefail
echo "Manual step: unplug the charger now, then press Enter."
read -r _
cd "$(dirname "$0")/../../core"
cargo run -p labd -- doctor | grep -E "power" || true
echo
echo "Expect: ❌ power ... on_ac=Some(false) — plug in + performance mode before a GPU demo"
