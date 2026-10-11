//! These run against the REAL laptop (nvidia-smi, /sys/class/power_supply).
//! Assertions are deliberately loose — the point is "this doesn't crash and
//! returns something plausible," not "this laptop has exactly X."

use lab_telemetry::{free_disk_gb, sample_gpu, sample_power, should_warn_power};

#[test]
fn gpu_sample_is_plausible_if_present() {
    if let Some(gpu) = sample_gpu() {
        assert!(gpu.name.is_some());
        if let Some(total) = gpu.mem_total_mib {
            assert!(total > 0.0, "GPU should report nonzero total VRAM");
        }
        if let Some(util) = gpu.util_pct {
            assert!((0.0..=100.0).contains(&util));
        }
    }
    // else: no nvidia-smi on this box — that's a valid outcome, not a failure
}

#[test]
fn free_disk_gb_reports_a_real_plausible_number_for_cwd() {
    // P12.2 "disk low" chaos drill's underlying primitive: can't safely
    // fill this machine's real disk just to test the rejection path, so
    // this proves the NUMBER is real and sane — the comparison that uses
    // it in lab-gateway's job-submit guard is a one-line `<` on this.
    let gb = free_disk_gb(".").expect("df should work on a real Linux dev/CI box");
    assert!(gb > 0.0, "a real machine always has SOME free space");
    assert!(gb < 100_000.0, "sanity ceiling — a parse bug could return something absurd");
}

#[test]
fn power_sample_does_not_crash_and_warn_logic_is_consistent() {
    let power = sample_power();
    let warn = should_warn_power(&power);
    if power.on_ac == Some(true) && power.profile.as_deref() == Some("performance") {
        assert!(!warn, "plugged in + performance mode must never warn");
    }
}
