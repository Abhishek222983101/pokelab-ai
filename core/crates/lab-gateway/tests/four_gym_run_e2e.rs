//! P11.6 — the "four-gym run": one `brain` connection submits a REAL job
//! for each of the four P11 paper kits (materials, distillation, nerf,
//! arena) back-to-back through the actual labd + WarmPool + Python
//! worker pipeline — not a unit test of each kit in isolation — and a
//! real client watches every one of them finish with status "ok" and
//! real final metrics. This is the backend proof the game's four Gym
//! leaders (one per paper) are genuinely fightable, not cosmetic.

use std::sync::Arc;

use futures_util::{SinkExt, StreamExt};
use lab_jobs::{PoolConfig, WarmPool};
use tokio_tungstenite::tungstenite::Message;

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
async fn four_new_paper_kits_run_end_to_end_through_the_real_pipeline() {
    let Some(python) = workers_python() else {
        eprintln!("skipping: workers/.venv not found");
        return;
    };

    let dir = tempfile::tempdir().unwrap();
    let store = Arc::new(lab_store::Store::open(dir.path().join("lab.db")).unwrap());
    let pool = WarmPool::spawn(PoolConfig {
        python, workers_cwd: workers_cwd(), n_slots: 1, device: "cpu".to_string(),
    })
    .await
    .unwrap();

    let secret = b"four-gym-secret".to_vec();
    let app = lab_gateway::router(store, secret.clone(), Some(pool));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let (mut client_ws, _) = tokio_tungstenite::connect_async(format!("ws://{addr}/api/ws"))
        .await
        .unwrap();
    client_ws.send(Message::Text(r#"{"type":"hello","since":0}"#.into())).await.unwrap();

    use tokio_tungstenite::tungstenite::handshake::client::generate_key;
    use tokio_tungstenite::tungstenite::http::Request;
    let req = Request::builder()
        .uri(format!("ws://{addr}/internal/brain"))
        .header("Authorization", format!("Bearer {}", String::from_utf8(secret).unwrap()))
        .header("Host", addr.to_string())
        .header("Connection", "Upgrade")
        .header("Upgrade", "websocket")
        .header("Sec-WebSocket-Version", "13")
        .header("Sec-WebSocket-Key", generate_key())
        .body(())
        .unwrap();
    let (mut brain_ws, _) = tokio_tungstenite::connect_async(req).await.unwrap();

    // the four real P11 gym leaders, each a genuinely different paper
    // kit, each with a deliberately small/fast config — this test
    // proves the PIPELINE, the kits' own result quality is proven by
    // their own unit tests in workers/tests/.
    let leaders: Vec<(&str, serde_json::Value)> = vec![
        ("materials", serde_json::json!({"n_estimators": 20, "trees_per_step": 10})),
        (
            "distillation",
            serde_json::json!({"n_total": 1500, "teacher_epochs": 15, "student_epochs": 30, "n_labeled": 100, "n_unlabeled": 800}),
        ),
        ("nerf", serde_json::json!({"downsample_factor": 10, "n_samples": 16, "iters": 20, "test_every": 10})),
        ("arena", serde_json::json!({"dataset": "magictelescope", "n_subsample": 600, "n_folds": 3})),
    ];

    for (kit, config) in leaders {
        let job_submit = serde_json::json!({"type": "job_submit", "req": kit, "kit": kit, "config": config});
        brain_ws.send(Message::Text(job_submit.to_string().into())).await.unwrap();
        let accepted_raw = brain_ws.next().await.unwrap().unwrap().into_text().unwrap();
        let accepted: serde_json::Value = serde_json::from_str(&accepted_raw).unwrap();
        assert_eq!(accepted["type"], "job_accepted", "{kit} job_submit rejected: {accepted}");
        let job_id = accepted["job_id"].as_str().unwrap().to_string();

        let mut saw_done = false;
        let mut saw_metric = false;
        let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(60);
        while tokio::time::Instant::now() < deadline && !saw_done {
            let Ok(Some(Ok(msg))) = tokio::time::timeout(std::time::Duration::from_secs(60), client_ws.next()).await else {
                break;
            };
            let text = msg.into_text().unwrap_or_default();
            let parsed: serde_json::Value = serde_json::from_str(&text).unwrap_or_default();
            if parsed["type"] != "event" {
                continue;
            }
            let e = &parsed["e"];
            if e["kind"] == "job.metric" && e["payload"]["job_id"] == job_id {
                saw_metric = true;
            }
            if e["kind"] == "job.done" && e["payload"]["job_id"] == job_id {
                assert_eq!(e["payload"]["status"], "ok", "{kit} job did not finish ok: {e}");
                assert!(e["payload"]["final"].is_object(), "{kit} job finished with no final metrics: {e}");
                saw_done = true;
            }
        }
        assert!(saw_metric, "{kit}: never saw a real job.metric event");
        assert!(saw_done, "{kit}: never saw job.done — timed out waiting on a real run");
    }
}
