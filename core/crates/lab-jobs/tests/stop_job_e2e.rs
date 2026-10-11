//! A REAL long-running job, stopped mid-flight through the Rust side's
//! stop_job — proves the fix in pool_main.py (a dedicated stdin reader
//! thread) actually works end to end from the Rust caller's point of view,
//! not just when driven directly from Python.

use lab_jobs::{PoolConfig, ProtocolLine, WarmPool};

fn workers_python() -> Option<String> {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../workers/.venv/bin/python");
    path.exists().then(|| path.to_string_lossy().into_owned())
}

fn workers_cwd() -> String {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../workers")
        .to_string_lossy()
        .into_owned()
}

#[tokio::test]
async fn stop_job_interrupts_a_real_running_job() {
    let Some(python) = workers_python() else {
        eprintln!("skipping: workers/.venv not found");
        return;
    };

    let mut pool = WarmPool::spawn(PoolConfig {
        python, workers_cwd: workers_cwd(), n_slots: 1, device: "cpu".to_string(),
    })
    .await
    .unwrap();

    let (job_id, mut rx) = pool
        .submit(
            "grokking",
            serde_json::json!({
                "model": "mlp", "p": 53, "frac": 0.5, "steps": 200000,
                "eval_every": 50, "device": "cpu", "d_hidden": 32, "d_emb": 16
            }),
        )
        .await
        .unwrap();

    // let it genuinely get into the training loop before stopping it
    tokio::time::sleep(std::time::Duration::from_millis(1500)).await;

    let stopped = pool.stop_job(&job_id).await.unwrap();
    assert!(stopped, "stop_job should have found the running job's slot");

    let mut final_steps_run: Option<i64> = None;
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(15);
    while tokio::time::Instant::now() < deadline {
        match tokio::time::timeout(std::time::Duration::from_secs(1), rx.recv()).await {
            Ok(Some(ProtocolLine::Done { status, final_, .. })) => {
                assert_eq!(status, "stopped");
                let steps_run = final_.as_ref().unwrap()["steps_run"].as_i64().unwrap();
                final_steps_run = Some(steps_run);
                break;
            }
            Ok(Some(_)) => continue,
            Ok(None) => break,
            Err(_) => continue,
        }
    }

    let steps_run = final_steps_run.expect("never got a Done line for the stopped job");
    assert!(steps_run < 200_000, "job ran to completion instead of being interrupted");
    assert!(steps_run < 50_000, "stop took far too long to take effect: steps_run={steps_run}");

    pool.shutdown().await;
}
