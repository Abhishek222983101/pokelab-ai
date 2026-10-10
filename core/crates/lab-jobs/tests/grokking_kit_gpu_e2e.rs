//! A REAL GPU grokking run through the Rust warm pool — not a stub, not a
//! smoke test. Takes ~15-90s. Skips (without failing) if torch/CUDA or the
//! workers venv aren't present, so CI on a GPU-less box still passes.

use lab_jobs::{PoolConfig, ProtocolLine, WarmPool};

/// Resolved from CARGO_MANIFEST_DIR, same reasoning as smoke_kit_e2e.rs: a
/// wrong relative path must never turn into a silently-skipped "ok".
fn workers_python() -> Option<String> {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../workers/.venv/bin/python");
    if path.exists() {
        Some(path.to_string_lossy().into_owned())
    } else {
        None
    }
}

fn workers_cwd() -> String {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../workers")
        .to_string_lossy()
        .into_owned()
}

#[tokio::test]
async fn grokking_kit_grokks_through_real_gpu_warm_pool() {
    let Some(python) = workers_python() else {
        eprintln!("skipping: workers/.venv not found");
        return;
    };
    let has_cuda = std::process::Command::new(&python)
        .args(["-I", "-c", "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"])
        .status()
        .map(|s| s.success())
        .unwrap_or(false);
    if !has_cuda {
        eprintln!("skipping: no CUDA GPU visible to torch");
        return;
    }

    std::env::set_var("WANDB_MODE", "offline");
    let cfg = PoolConfig {
        python,
        workers_cwd: workers_cwd(),
        n_slots: 1,
        device: "cuda".to_string(),
    };
    let mut pool = WarmPool::spawn(cfg).await.unwrap();

    let (_job_id, lines) = pool
        .submit_and_collect(
            "grokking",
            serde_json::json!({
                "model": "transformer", "p": 113, "frac": 0.5, "wd": 1.0,
                "steps": 20000, "eval_every": 200, "device": "cuda",
                "stop_at": 0.95, "project": "grokking-rust-e2e"
            }),
        )
        .await
        .unwrap();

    let test_accs: Vec<f64> = lines
        .iter()
        .filter_map(|l| match l {
            ProtocolLine::Metric { k, v, .. } if k == "test_acc" => *v,
            _ => None,
        })
        .collect();
    assert!(!test_accs.is_empty(), "grokking kit must emit test_acc metrics");
    let final_acc = *test_accs.last().unwrap();
    assert!(final_acc >= 0.95, "expected to grok (test_acc >= 0.95), got {final_acc}");

    match lines.last().unwrap() {
        ProtocolLine::Done { status, .. } => assert_eq!(status, "ok"),
        other => panic!("expected Done, got {other:?}"),
    }

    pool.shutdown().await;
}
