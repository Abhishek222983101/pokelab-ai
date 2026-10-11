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
        check_ram(),
        check_assets(),
        check_datasets(),
        check_web_out(),
        check_tunnel_binary(),
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

const MIN_FREE_RAM_GB: f64 = 3.0; // §14-refs R5: warm worker 1.17 GB each + browser

fn check_ram() -> CheckResult {
    // /proc/meminfo's MemAvailable (not MemFree) is the real "can I
    // allocate this much without swapping" number — the same one `free`
    // reports as "available".
    let meminfo = std::fs::read_to_string("/proc/meminfo");
    let avail_gb = meminfo.ok().and_then(|text| {
        text.lines()
            .find(|l| l.starts_with("MemAvailable:"))
            .and_then(|l| l.split_whitespace().nth(1))
            .and_then(|kb| kb.parse::<f64>().ok())
            .map(|kb| kb / 1024.0 / 1024.0)
    });
    match avail_gb {
        Some(gb) => CheckResult {
            name: "ram",
            ok: gb >= MIN_FREE_RAM_GB,
            detail: format!("{gb:.1} GiB available (need >= {MIN_FREE_RAM_GB} GiB, §14-refs R5)"),
        },
        None => CheckResult {
            name: "ram",
            ok: false,
            detail: "could not read /proc/meminfo".to_string(),
        },
    }
}

fn check_web_out() -> CheckResult {
    let index = Path::new("../web/out/index.html");
    let manifest = Path::new("../web/public/assets/gen/manifest.json");
    let web_ok = index.is_file();
    let atlases_ok = manifest.is_file();
    CheckResult {
        name: "web_build",
        ok: web_ok && atlases_ok,
        detail: match (web_ok, atlases_ok) {
            (true, true) => "web/out built, atlases generated".to_string(),
            (false, _) => "web/out missing — run `npm run build` in web/".to_string(),
            (_, false) => "assets/gen/manifest.json missing — run `python assets/build_atlases.py`".to_string(),
        },
    }
}

fn check_tunnel_binary() -> CheckResult {
    let found = std::process::Command::new("which")
        .arg("cloudflared")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);
    CheckResult {
        name: "tunnel_binary",
        ok: true, // not having it is fine unless the demo specifically needs a public URL
        detail: if found {
            "cloudflared on PATH".to_string()
        } else {
            "cloudflared not found — scripts/tunnel.sh (remote viewing) unavailable, local demo unaffected".to_string()
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
    // [BUG FOUND & FIXED, P12.1]: this used to check `../data/raw/<name>`,
    // a convention fetch_datasets.sh expected but nothing ever actually
    // wrote to — the P11 kits (materials/arena/distillation/nerf) cache
    // their real OpenML/tiny_nerf downloads under workers/var/data/
    // instead (data_home.py), so this check always failed regardless of
    // whether the datasets were really present. Checking the real paths.
    let openml_cache_present = Path::new("../workers/var/data/sklearn_cache/openml").is_dir();
    let tiny_nerf_present = Path::new("../workers/var/data/tiny_nerf_data.npz").is_file();
    let missing: Vec<&str> = [
        (!openml_cache_present).then_some("openml datasets (materials/arena/distillation)"),
        (!tiny_nerf_present).then_some("tiny_nerf_data.npz (nerf)"),
    ]
    .into_iter()
    .flatten()
    .collect();
    // Not a hard requirement: every kit using one of these fetches it on
    // its own first real run (and caches it after). This check is a
    // pre-warm status report, not a pass/fail gate — a cold demo just
    // pays a one-time download on its first job of that kit.
    CheckResult {
        name: "datasets",
        ok: true,
        detail: if missing.is_empty() {
            "real OpenML cache + tiny_nerf_data.npz already pre-warmed under workers/var/data/".to_string()
        } else {
            format!(
                "not pre-warmed yet (each kit self-fetches on first real run, no action needed): {}",
                missing.join(", ")
            )
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn run_returns_one_result_per_real_check_with_a_name_and_detail() {
        let results = run();
        assert_eq!(results.len(), 10, "P12.1: every §5.10 system-level check labd owns");
        let names: Vec<&str> = results.iter().map(|r| r.name).collect();
        assert_eq!(
            names,
            vec!["gpu", "power", "disk", "ram", "assets", "datasets", "web_build", "tunnel_binary", "workers_venv", "env_keys"]
        );
        for r in &results {
            assert!(!r.detail.is_empty(), "{} has an empty detail string", r.name);
        }
    }

    #[test]
    fn ram_check_reads_the_real_proc_meminfo_on_this_machine() {
        let result = check_ram();
        // this machine really has /proc/meminfo (Linux CI/dev box) — a
        // parse failure here is a real bug, not an environment quirk
        assert!(!result.detail.contains("could not read"), "{}", result.detail);
    }

    #[test]
    fn tunnel_binary_check_never_fails_the_whole_doctor() {
        // absence is a warning (remote viewing unavailable), never a
        // reason to block a local-only demo
        assert!(check_tunnel_binary().ok);
    }
}
