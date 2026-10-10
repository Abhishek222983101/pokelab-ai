//! Spawns the REAL python worker (pokelab_workers.pool_main) as a child
//! process and runs the `smoke` kit through the full stdin/stdout protocol.
//! Skips (without failing CI) if the workers venv hasn't been `uv sync`'d.

use lab_jobs::{PoolConfig, ProtocolLine, WarmPool};

/// Resolved from CARGO_MANIFEST_DIR (this crate's own directory), never from
/// the test binary's cwd — a relative guess here silently skips the test
/// instead of failing, which is worse than wrong: it looks green.
fn workers_python() -> Option<String> {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let path = std::path::Path::new(manifest_dir)
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
async fn smoke_kit_runs_through_real_python_worker() {
    let Some(python) = workers_python() else {
        eprintln!("skipping: workers/.venv not found, run `uv sync` in workers/ first");
        return;
    };

    let cfg = PoolConfig {
        python,
        workers_cwd: workers_cwd(),
        n_slots: 1,
        device: "cpu".to_string(),
    };
    let mut pool = WarmPool::spawn(cfg).await.unwrap();
    assert_eq!(pool.free_slots(), 1);

    let (job_id, lines) = pool
        .submit_and_collect("smoke", serde_json::json!({"n_steps": 10}))
        .await
        .unwrap();

    assert!(job_id.starts_with("job-"));
    let metrics: Vec<_> = lines
        .iter()
        .filter_map(|l| match l {
            ProtocolLine::Metric { step, k, v, .. } => Some((*step, k.clone(), *v)),
            _ => None,
        })
        .collect();
    assert_eq!(metrics.len(), 10);
    assert_eq!(metrics[0].0, 1);
    assert_eq!(metrics[0].1, "loss");
    assert!(metrics[0].2.unwrap() < 1.0);

    let done = lines.last().unwrap();
    match done {
        ProtocolLine::Done { status, final_, .. } => {
            assert_eq!(status, "ok");
            assert_eq!(final_.as_ref().unwrap()["n_steps"], 10);
        }
        other => panic!("expected Done, got {other:?}"),
    }

    assert_eq!(pool.free_slots(), 1, "slot must be freed after Done");

    // the warm process is reused for a second job — prove the slot is still alive
    let (_job2, lines2) = pool
        .submit_and_collect("smoke", serde_json::json!({"n_steps": 3}))
        .await
        .unwrap();
    assert!(lines2
        .iter()
        .any(|l| matches!(l, ProtocolLine::Done { status, .. } if status == "ok")));

    pool.shutdown().await;
}
