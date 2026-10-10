//! `labd doctor`: the preflight check (§4.6, §11.2). Runs real probes
//! against this machine — nothing here is simulated — and prints a
//! pass/warn/fail line per check, matching the model every other NFR
//! response in the system follows: show the user what's actually true.

use std::path::Path;

pub struct CheckResult {
    pub name: &'static str,
    pub ok: bool,
    pub detail: String,
}

pub fn run() -> Vec<CheckResult> {
    vec![
        check_gpu(),
        check_power(),
        check_disk(),
        check_assets(),
        check_datasets(),
        check_workers_venv(),
        check_env_keys(),
    ]
}

fn check_gpu() -> CheckResult {
    match lab_telemetry::sample_gpu() {
        Some(gpu) => CheckResult {
            name: "gpu",
            ok: true,
            detail: format!(
                "{} — {:.0}% util, {:.0}/{:.0} MiB VRAM",
                gpu.name.unwrap_or_default(),
                gpu.util_pct.unwrap_or(0.0),
                gpu.mem_used_mib.unwrap_or(0.0),
                gpu.mem_total_mib.unwrap_or(0.0)
            ),
        },
        None => CheckResult {
            name: "gpu",
            ok: false,
            detail: "no nvidia-smi / no GPU visible — GPU kits will fail".to_string(),
        },
    }
}

fn check_power() -> CheckResult {
    let power = lab_telemetry::sample_power();
    let warn = lab_telemetry::should_warn_power(&power);
    CheckResult {
        name: "power",
        ok: !warn,
        detail: format!(
            "on_ac={:?} profile={:?}{}",
            power.on_ac,
            power.profile,
            if warn {
                " — plug in + performance mode before a GPU demo (runs ~3x slower otherwise)"
            } else {
                ""
            }
        ),
    }
}

const MIN_FREE_GB: i64 = 3; // §11.2: refuse new artifacts below this

fn check_disk() -> CheckResult {
    // statvfs via std is unstable; shell to `df` is the pragmatic, portable
    // choice here (same approach lab-telemetry already takes for power).
    let out = std::process::Command::new("df")
        .args(["-BG", "--output=avail", "."])
        .output();
    match out {
        Ok(o) if o.status.success() => {
            let text = String::from_utf8_lossy(&o.stdout);
            let avail_gb: i64 = text
                .lines()
                .nth(1)
                .and_then(|l| l.trim().trim_end_matches('G').parse().ok())
                .unwrap_or(-1);
            CheckResult {
                name: "disk",
                ok: !(0..MIN_FREE_GB).contains(&avail_gb),
                detail: format!("{avail_gb} GiB free (need >= 3 GiB, §11.2)"),
            }
        }
        _ => CheckResult {
            name: "disk",
            ok: false,
            detail: "could not run `df`".to_string(),
        },
    }
}

fn check_assets() -> CheckResult {
    let dir = Path::new("../assets/vendor/showdown");
    let ok = dir.is_dir() && dir.read_dir().map(|mut r| r.next().is_some()).unwrap_or(false);
    CheckResult {
        name: "assets",
        ok,
        detail: if ok {
            "assets/vendor/showdown present".to_string()
        } else {
            "missing — run `just fetch`".to_string()
        },
    }
}

fn check_datasets() -> CheckResult {
    let needed = ["mnist", "tiny_nerf", "matbench_expt_gap", "matbench_steels", "tabular"];
    let missing: Vec<&str> = needed
        .iter()
        .filter(|d| !Path::new(&format!("../data/raw/{d}")).is_dir())
        .copied()
        .collect();
    CheckResult {
        name: "datasets",
        ok: missing.is_empty(),
        detail: if missing.is_empty() {
            format!("{} datasets present", needed.len())
        } else {
            format!("missing: {} — run `just fetch`", missing.join(", "))
        },
    }
}

fn check_workers_venv() -> CheckResult {
    let ok = Path::new("../workers/.venv/bin/python").exists();
    CheckResult {
        name: "workers_venv",
        ok,
        detail: if ok {
            "workers/.venv present".to_string()
        } else {
            "missing — run `uv sync` in workers/".to_string()
        },
    }
}

fn check_env_keys() -> CheckResult {
    // presence only — values are never read into this process, let alone
    // printed (labd only ever needs LABD_BRAIN_SECRET / LABD_PAIRING_SECRET
    // for itself; the LLM/W&B keys belong to brain and scripts/wandb_sync.sh)
    let present = |k: &str| std::env::var(k).map(|v| !v.is_empty()).unwrap_or(false);
    let checks = [
        ("LABD_BRAIN_SECRET", present("LABD_BRAIN_SECRET")),
        ("LABD_PAIRING_SECRET", present("LABD_PAIRING_SECRET")),
    ];
    let missing: Vec<&str> = checks.iter().filter(|(_, ok)| !ok).map(|(k, _)| *k).collect();
    CheckResult {
        name: "env_keys",
        ok: missing.is_empty(),
        detail: if missing.is_empty() {
            "LABD_BRAIN_SECRET, LABD_PAIRING_SECRET set".to_string()
        } else {
            format!("missing: {} — run `just init`", missing.join(", "))
        },
    }
}
