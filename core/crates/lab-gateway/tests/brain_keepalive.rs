//! A keep-alive Ping on /internal/brain must NOT close the session (it used to: any non-text frame
//! made labd hang up, so the brain was dropped ~20 s after connecting, mid-project).

use std::sync::Arc;

use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::tungstenite::{client::IntoClientRequest, Message};

#[tokio::test]
async fn ping_frames_do_not_drop_the_brain() {
    let dir = tempfile::tempdir().unwrap();
    let store = Arc::new(lab_store::Store::open(dir.path().join("lab.db")).unwrap());
    let app = lab_gateway::router(store, b"s3cret".to_vec(), None);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

    let mut req = format!("ws://{addr}/internal/brain").into_client_request().unwrap();
    req.headers_mut().insert("authorization", "Bearer s3cret".parse().unwrap());
    let (mut ws, _) = tokio_tungstenite::connect_async(req).await.unwrap();

    ws.send(Message::Ping(vec![1, 2, 3].into())).await.unwrap();
    ws.send(Message::Pong(vec![].into())).await.unwrap();

    // the session must still answer a real publish after the control frames
    let publish = r#"{"type":"publish","req":"r1","events":[{"kind":"agent.thought","v":1,"project":null,"actor":"oak","corr":null,"causation":null,"payload":{"text":"hi"},"display":null}]}"#;
    ws.send(Message::Text(publish.into())).await.unwrap();
    let mut got = false;
    for _ in 0..5 {
        let m = tokio::time::timeout(std::time::Duration::from_secs(3), ws.next()).await.expect("session was closed after a ping").unwrap().unwrap();
        if let Message::Text(t) = m {
            if t.contains("\"published\"") { got = true; break; }
        }
    }
    assert!(got, "no `published` reply after Ping/Pong");
}
