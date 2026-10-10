//! End-to-end: a fake "brain" connects over /internal/brain, submits a real
//! `smoke` kit job through the REAL python warm pool, and a fake "client"
//! connected over /api/ws sees the resulting job.metric/job.done events —
//! proving the whole chain (auth -> job engine -> event store -> broadcast
//! -> WS fan-out) in one real run, not mocks.

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
async fn brain_submits_job_and_client_sees_it_live() {
    let Some(python) = workers_python() else {
        eprintln!("skipping: workers/.venv not found");
        return;
    };

    let dir = tempfile::tempdir().unwrap();
    let store = Arc::new(lab_store::Store::open(dir.path().join("lab.db")).unwrap());
    let pool = WarmPool::spawn(PoolConfig {
        python,
        workers_cwd: workers_cwd(),
        n_slots: 1,
        device: "cpu".to_string(),
    })
    .await
    .unwrap();

    let secret = b"test-brain-secret".to_vec();
    let app = lab_gateway::router(store, secret.clone(), Some(pool));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    // --- client connects first and says hello (since=0) ---
    let (mut client_ws, _) = tokio_tungstenite::connect_async(format!("ws://{addr}/api/ws"))
        .await
        .unwrap();
    client_ws
        .send(Message::Text(r#"{"type":"hello","since":0}"#.into()))
        .await
        .unwrap();

    // --- "brain" connects with the bearer secret and submits a job ---
    use tokio_tungstenite::tungstenite::http::Request;
    let req = Request::builder()
        .uri(format!("ws://{addr}/internal/brain"))
        .header("Authorization", format!("Bearer {}", String::from_utf8(secret).unwrap()))
        .header("Host", addr.to_string())
        .header("Connection", "Upgrade")
        .header("Upgrade", "websocket")
        .header("Sec-WebSocket-Version", "13")
        .header("Sec-WebSocket-Key", tokio_tungstenite::tungstenite::handshake::client::generate_key())
        .body(())
        .unwrap();
    let (mut brain_ws, _) = tokio_tungstenite::connect_async(req).await.unwrap();

    brain_ws
        .send(Message::Text(
            r#"{"type":"job_submit","req":"r1","kit":"smoke","config":{"n_steps":5}}"#.into(),
        ))
        .await
        .unwrap();

    // brain should get job_accepted
    let accepted = tokio::time::timeout(std::time::Duration::from_secs(5), brain_ws.next())
        .await
        .expect("timed out waiting for job_accepted")
        .unwrap()
        .unwrap();
    let accepted_text = accepted.into_text().unwrap();
    assert!(accepted_text.contains("job_accepted"), "{accepted_text}");

    // client should see job.metric and job.done events live, without ever
    // having to poll — this is the actual point of the WS hub existing
    let mut saw_metric = false;
    let mut saw_done = false;
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(10);
    while tokio::time::Instant::now() < deadline && !saw_done {
        let Ok(Some(Ok(msg))) =
            tokio::time::timeout(std::time::Duration::from_secs(10), client_ws.next()).await
        else {
            break;
        };
        let text = msg.into_text().unwrap_or_default();
        if text.contains("job.metric") {
            saw_metric = true;
        }
        if text.contains("job.done") {
            saw_done = true;
        }
    }

    assert!(saw_metric, "client never saw a job.metric event over /api/ws");
    assert!(saw_done, "client never saw the job.done event over /api/ws");
}
