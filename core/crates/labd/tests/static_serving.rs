//! A REAL labd instance serving the REAL static export from web/ — not a
//! stub. Skips (without failing) if `web/out` hasn't been built yet.

#[tokio::test]
async fn labd_serves_the_real_static_export() {
    let web_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../web/out");
    if !web_dir.is_dir() {
        eprintln!("skipping: web/out not built — run `npm run build` in web/");
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let store = std::sync::Arc::new(lab_store::Store::open(dir.path().join("lab.db")).unwrap());
    let app = lab_gateway::router_with_web(store, b"test".to_vec(), None, Some(web_dir));

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let client = reqwest::Client::new();
    let resp = client.get(format!("http://{addr}/")).send().await.unwrap();
    assert_eq!(resp.status(), 200);
    let body = resp.text().await.unwrap();
    assert!(body.contains("PokéLab") || body.contains("Pok\u{e9}Lab"), "expected the real page title in the served HTML");

    // the API routes must still work alongside the static fallback
    let health = client.get(format!("http://{addr}/api/health")).send().await.unwrap();
    assert_eq!(health.status(), 200);

    // a nested route (trailingSlash: true in next.config.ts exports
    // console/index.html — without it this 404s, see docs/PROGRESS.md P8.2)
    let console_resp = client.get(format!("http://{addr}/console/")).send().await.unwrap();
    assert_eq!(console_resp.status(), 200);
    let console_body = console_resp.text().await.unwrap();
    assert!(console_body.contains("Console"));
}
