//! These run against the REAL laptop (nvidia-smi, /sys/class/power_supply).
//! Assertions are deliberately loose — the point is "this doesn't crash and
//! returns something plausible," not "this laptop has exactly X."

use lab_telemetry::{sample_gpu, sample_power, should_warn_power};

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
fn power_sample_does_not_crash_and_warn_logic_is_consistent() {
    let power = sample_power();
    let warn = should_warn_power(&power);
    if power.on_ac == Some(true) && power.profile.as_deref() == Some("performance") {
        assert!(!warn, "plugged in + performance mode must never warn");
    }
}
