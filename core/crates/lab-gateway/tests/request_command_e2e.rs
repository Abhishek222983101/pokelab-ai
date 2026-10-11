//! A researcher's plain-words request (console or phone) becomes a real `project.requested` event
//! that Oak picks up — labd only records the intent, it never interprets it (§3.3.2).

use std::sync::Arc;

use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::tungstenite::Message;

async fn next_json(ws: &mut (impl StreamExt<Item = Result<Message, tokio_tungstenite::tungstenite::Error>> + Unpin)) -> serde_json::Value {
    let msg = tokio::time::timeout(std::time::Duration::from_secs(5), ws.next()).await.unwrap().unwrap().unwrap();
    serde_json::from_str(&msg.into_text().unwrap()).unwrap()
}

#[tokio::test]
async fn request_and_feedback_commands_become_events() {
    let dir = tempfile::tempdir().unwrap();
    let store = Arc::new(lab_store::Store::open(dir.path().join("lab.db")).unwrap());
    let app = lab_gateway::router(store, b"s".to_vec(), None);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

    let (mut ws, _) = tokio_tungstenite::connect_async(format!("ws://{addr}/api/ws")).await.unwrap();
    ws.send(Message::Text(r#"{"type":"hello","since":0}"#.into())).await.unwrap();

    // empty text is refused, nothing is recorded
    ws.send(Message::Text(r#"{"type":"command","command":"request","text":"   "}"#.into())).await.unwrap();
    let r = next_json(&mut ws).await;
    assert_eq!(r["type"], "command_result");
    assert_eq!(r["ok"], false);

    ws.send(Message::Text(r#"{"type":"command","command":"request","text":"Reproduce grokking"}"#.into())).await.unwrap();
    let mut saw_ok = false;
    let mut saw_event = false;
    for _ in 0..4 {
        let m = next_json(&mut ws).await;
        if m["type"] == "command_result" && m["command"] == "request" { assert_eq!(m["ok"], true, "{m}"); saw_ok = true; }
        if m["type"] == "event" && m["e"]["kind"] == "project.requested" {
            assert_eq!(m["e"]["payload"]["text"], "Reproduce grokking");
            assert_eq!(m["e"]["actor"], "human");
            saw_event = true;
        }
        if saw_ok && saw_event { break; }
    }
    assert!(saw_ok && saw_event);

    // feedback outside [0,1] is refused
    ws.send(Message::Text(r#"{"type":"command","command":"feedback","agent_id":"pikachu","value":2.0}"#.into())).await.unwrap();
    let r = next_json(&mut ws).await;
    assert_eq!(r["ok"], false);
}
