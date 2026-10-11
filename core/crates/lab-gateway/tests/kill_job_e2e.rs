//! A client connects to /api/ws, a brain submits a REAL long-running job
//! over /internal/brain, the client sends a kill_job command, and the
//! job actually stops — proven by watching job.done{status:"stopped"}
//! arrive over the SAME client socket.

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
async fn client_kills_a_real_running_job_over_api_ws() {
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

    let secret = b"kill-test-secret".to_vec();
    let app = lab_gateway::router(store, secret.clone(), Some(pool));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    // --- client connects and says hello ---
    let (mut client_ws, _) = tokio_tungstenite::connect_async(format!("ws://{addr}/api/ws"))
        .await
        .unwrap();
    client_ws.send(Message::Text(r#"{"type":"hello","since":0}"#.into())).await.unwrap();

    // --- "brain" submits a long-running job ---
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

    let job_submit = serde_json::json!({
        "type": "job_submit", "req": "r1", "kit": "grokking",
        "config": {"model": "mlp", "p": 53, "frac": 0.5, "steps": 200000,
                   "eval_every": 50, "device": "cpu", "d_hidden": 32, "d_emb": 16}
    });
    brain_ws.send(Message::Text(job_submit.to_string().into())).await.unwrap();
    let accepted_raw = brain_ws.next().await.unwrap().unwrap().into_text().unwrap();
    let accepted: serde_json::Value = serde_json::from_str(&accepted_raw).unwrap();
    assert_eq!(accepted["type"], "job_accepted");
    let job_id = accepted["job_id"].as_str().unwrap().to_string();

    // give it time to actually be mid-training before we kill it
    tokio::time::sleep(std::time::Duration::from_millis(1500)).await;

    // --- client sends kill_job ---
    let kill_cmd = serde_json::json!({"type": "command", "command": "kill_job", "job_id": job_id});
    client_ws.send(Message::Text(kill_cmd.to_string().into())).await.unwrap();

    // --- watch for command_result AND the job actually stopping ---
    let mut saw_command_ok = false;
    let mut saw_stopped = false;
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(15);
    while tokio::time::Instant::now() < deadline && !(saw_command_ok && saw_stopped) {
        let Ok(Some(Ok(msg))) = tokio::time::timeout(std::time::Duration::from_secs(5), client_ws.next()).await else {
            break;
        };
        let text = msg.into_text().unwrap_or_default();
        let parsed: serde_json::Value = serde_json::from_str(&text).unwrap_or_default();
        if parsed["type"] == "command_result" && parsed["command"] == "kill_job" {
            assert_eq!(parsed["ok"], true, "kill_job command_result: {parsed}");
            saw_command_ok = true;
        }
        if parsed["type"] == "event" && parsed["e"]["kind"] == "job.done" {
            assert_eq!(parsed["e"]["payload"]["status"], "stopped");
            saw_stopped = true;
        }
    }

    assert!(saw_command_ok, "never got command_result for kill_job");
    assert!(saw_stopped, "job never actually stopped");
}
