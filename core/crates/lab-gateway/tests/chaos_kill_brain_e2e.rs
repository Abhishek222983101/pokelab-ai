//! P12.2 chaos drill — "kill brain mid-project": the `brain` connection
//! that submitted a job disconnects immediately after submitting it
//! (simulating Oak's process crashing, or losing network, mid-run) —
//! and a REAL client watching over /api/ws still sees that job run to
//! completion with real metrics and a real Done. Jobs live in the warm
//! pool, independent of whoever submitted them; this is what makes that
//! true, not an assumption.
//!
//! Honest limitation this drill surfaces (not fixed here, scope for a
//! future phase): there is no actual process supervisor that restarts a
//! crashed `brain` with backoff (§5.2/P1.7's architecture doc mentions
//! one; it was never built — `just up` starts labd and the web dev
//! server, not a brain child process). What's real today: labd itself
//! doesn't need brain alive to keep a job running, and a reconnecting
//! brain gets the full event backlog via Subscribe{since}. A full
//! auto-restart-with-backoff supervisor is NOT implemented.

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
async fn job_survives_the_submitting_brain_connection_dying() {
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

    let secret = b"chaos-kill-brain-secret".to_vec();
    let app = lab_gateway::router(store, secret.clone(), Some(pool));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    // a real client is already watching, independent of brain
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

    let job_submit = serde_json::json!({"type": "job_submit", "req": "r1", "kit": "smoke", "config": {"n_steps": 200}});
    brain_ws.send(Message::Text(job_submit.to_string().into())).await.unwrap();
    let accepted_raw = brain_ws.next().await.unwrap().unwrap().into_text().unwrap();
    let accepted: serde_json::Value = serde_json::from_str(&accepted_raw).unwrap();
    let job_id = accepted["job_id"].as_str().unwrap().to_string();

    // "kill brain": close its connection right now, before the job (which
    // has not even started running real steps yet) has produced a single
    // metric. No clean disconnect, no goodbye message.
    drop(brain_ws);

    let mut saw_metric = false;
    let mut saw_done_ok = false;
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(15);
    while tokio::time::Instant::now() < deadline && !saw_done_ok {
        let Ok(Some(Ok(msg))) = tokio::time::timeout(std::time::Duration::from_secs(10), client_ws.next()).await else {
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
            assert_eq!(e["payload"]["status"], "ok", "job did not finish ok after brain died: {e}");
            saw_done_ok = true;
        }
    }
    assert!(saw_metric, "job never produced a real metric after brain disconnected");
    assert!(saw_done_ok, "job never finished — it depended on brain staying connected, which it should not");
}
