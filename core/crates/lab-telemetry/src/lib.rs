//! lab-telemetry: 1 Hz GPU/power/CPU telemetry (§5.7). Shells out to
//! `nvidia-smi` for GPU stats (no NVML FFI dependency needed for this) and
//! reads `/sys` for AC/power-profile state. Every read degrades gracefully
//! — a laptop with no NVIDIA GPU, or no `powerprofilesctl`, still boots.

use std::process::Command;

#[derive(Debug, Clone, Default)]
pub struct GpuSample {
    pub name: Option<String>,
    pub util_pct: Option<f64>,
    pub mem_used_mib: Option<f64>,
    pub mem_total_mib: Option<f64>,
    pub power_w: Option<f64>,
    pub temp_c: Option<f64>,
}

#[derive(Debug, Clone, Default)]
pub struct PowerSample {
    pub on_ac: Option<bool>,
    pub profile: Option<String>,
}

/// One nvidia-smi call, parsed. Returns None if nvidia-smi isn't installed
/// or there's no GPU — callers treat that as "no telemetry", not an error.
pub fn sample_gpu() -> Option<GpuSample> {
    let out = Command::new("nvidia-smi")
        .args([
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&out.stdout);
    let line = text.lines().next()?;
    let fields: Vec<&str> = line.split(',').map(str::trim).collect();
    if fields.len() < 6 {
        return None;
    }
    Some(GpuSample {
        name: Some(fields[0].to_string()),
        util_pct: fields[1].parse().ok(),
        mem_used_mib: fields[2].parse().ok(),
        mem_total_mib: fields[3].parse().ok(),
        power_w: fields[4].parse().ok(),
        temp_c: fields[5].parse().ok(),
    })
}

/// AC power + the active power profile. `[MEASURED, §5.7]`: on this laptop
/// `/sys/firmware/acpi/platform_profile` errors, so we shell out to
/// `powerprofilesctl` first and only fall back to the cpufreq sysfs knob.
pub fn sample_power() -> PowerSample {
    let on_ac = std::fs::read_dir("/sys/class/power_supply")
        .ok()
        .and_then(|entries| {
            entries.flatten().find_map(|e| {
                let name = e.file_name().to_string_lossy().to_string();
                if !name.starts_with('A') {
                    return None;
                }
                std::fs::read_to_string(e.path().join("online"))
                    .ok()
                    .map(|s| s.trim() == "1")
            })
        });

    let profile = Command::new("powerprofilesctl")
        .arg("get")
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .or_else(|| {
            std::fs::read_to_string("/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference")
                .ok()
                .map(|s| s.trim().to_string())
        });

    PowerSample { on_ac, profile }
}

/// §5.7's warning condition: a GPU job is running, but we're not plugged in
/// and in performance mode. `[MEASURED]` this laptop runs ~3–3.5x slower.
pub fn should_warn_power(power: &PowerSample) -> bool {
    let not_plugged = power.on_ac == Some(false);
    let not_performance = power
        .profile
        .as_deref()
        .map(|p| p != "performance")
        .unwrap_or(false);
    not_plugged || not_performance
}
