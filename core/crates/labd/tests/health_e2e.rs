use std::sync::Arc;

#[tokio::test]
async fn health_and_events_since_respond() {
    let dir = tempfile::tempdir().unwrap();
    let db_path = dir.path().join("lab.db");
    let store = Arc::new(lab_store::Store::open(&db_path).unwrap());

    // seed one event so /api/events/since has something real to return
    store
        .append(lab_store::NewEvent {
            kind: "agent.spawned".into(),
            v: 1,
            project: Some("p1".into()),
            actor: "test".into(),
            corr: None,
            causation: None,
            payload: serde_json::json!({"species": "eevee"}),
            display: None,
        })
        .unwrap();

    let app = lab_gateway::router(store, b"test-secret".to_vec());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{addr}");
    let client = reqwest::Client::new();

    let health: serde_json::Value = client
        .get(format!("{base}/api/health"))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert_eq!(health["status"], "ok");
    assert_eq!(health["latest_seq"], 1);

    let events: Vec<lab_store::Event> = client
        .get(format!("{base}/api/events/since?after=0"))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].kind, "agent.spawned");
    assert_eq!(events[0].payload["species"], "eevee");
}
