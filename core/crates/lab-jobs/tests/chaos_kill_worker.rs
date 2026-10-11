//! P12.2 chaos drill — "kill worker mid-run": SIGKILLs a slot's real
//! Python worker process while a real job is running on it, and proves
//! the caller gets a real Done{status:"error"} instead of hanging
//! forever. [BUG FOUND]: before lib.rs's EOF handler was fixed, this
//! test hung until its own timeout — the receiver never got anything.

use lab_jobs::{PoolConfig, WarmPool};

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
async fn killing_the_worker_process_surfaces_a_real_error_not_a_hang() {
    let Some(python) = workers_python() else {
        eprintln!("skipping: workers/.venv not found");
        return;
    };

    let mut pool = WarmPool::spawn(PoolConfig {
        python, workers_cwd: workers_cwd(), n_slots: 1, device: "cpu".to_string(),
    })
    .await
    .unwrap();

    // a job that would run for a while if the worker stayed alive
    let (job_id, mut rx) = pool
        .submit("smoke", serde_json::json!({"n_steps": 5000}))
        .await
        .unwrap();

    // give it a moment to actually start, then kill the process directly
    // — not stop_job's clean stdin command, a real SIGKILL
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    pool.kill_slot_process(0).await.unwrap();

    let result = tokio::time::timeout(std::time::Duration::from_secs(10), rx.recv()).await;
    let line = result.expect("receiver hung — the worker-death case is still unhandled").expect("channel closed with no Done at all");

    match line {
        lab_jobs::ProtocolLine::Done { job_id: done_id, status, error_sig, .. } => {
            assert_eq!(done_id, job_id);
            assert_eq!(status, "error");
            assert!(error_sig.unwrap().contains("exited unexpectedly"));
        }
        other => panic!("expected a Done{{status:\"error\"}}, got {other:?}"),
    }
}
