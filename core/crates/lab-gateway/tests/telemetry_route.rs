//! /api/telemetry returns the real nvidia-smi sample, or `gpu: null` — never a made-up number.

use std::sync::Arc;

#[tokio::test]
async fn telemetry_reports_real_gpu_or_null() {
    let dir = tempfile::tempdir().unwrap();
    let store = Arc::new(lab_store::Store::open(dir.path().join("lab.db")).unwrap());
    let app = lab_gateway::router(store, b"s".to_vec(), None);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    let mut tcp = tokio::net::TcpStream::connect(addr).await.unwrap();
    tcp.write_all(b"GET /api/telemetry HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n").await.unwrap();
    let mut raw = String::new();
    tcp.read_to_string(&mut raw).await.unwrap();
    assert!(raw.starts_with("HTTP/1.1 200"), "{raw}");
    let body = raw.split("\r\n\r\n").nth(1).unwrap().to_string();
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    let expected = lab_telemetry::sample_gpu();
    match (&v["gpu"], expected) {
        (serde_json::Value::Null, None) => {}
        (g, Some(s)) => {
            assert_eq!(g["mem_total_mib"].as_f64(), s.mem_total_mib, "{body}");
            let util = g["util_pct"].as_f64().unwrap();
            assert!((0.0..=100.0).contains(&util), "{body}");
        }
        (g, None) => panic!("route reported a GPU ({g}) that nvidia-smi does not see"),
    }
}
