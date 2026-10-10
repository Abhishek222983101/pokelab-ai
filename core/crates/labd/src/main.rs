//! labd: the PokéLab core daemon. Boots the event store and serves the
//! gateway's HTTP/WS API. Job engine, telemetry and supervision land across
//! the rest of P1.

use std::sync::Arc;

use anyhow::Context;

fn default_port() -> u16 {
    7700
}

fn default_db_path() -> std::path::PathBuf {
    std::path::PathBuf::from("../var/lab.db")
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let db_path = std::env::var("LABD_DB_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| default_db_path());
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).context("creating var/ for lab.db")?;
    }

    let store = Arc::new(lab_store::Store::open(&db_path).context("opening lab.db")?);
    tracing::info!(?db_path, "lab-store opened");

    let port: u16 = std::env::var("LABD_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or_else(default_port);

    let brain_secret = std::env::var("LABD_BRAIN_SECRET")
        .unwrap_or_else(|_| "dev-only-insecure-secret-set-LABD_BRAIN_SECRET".to_string())
        .into_bytes();
    let app = lab_gateway::router(store, brain_secret);
    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .with_context(|| format!("binding {addr}"))?;
    tracing::info!(%addr, "labd listening");
    axum::serve(listener, app).await.context("serving")?;
    Ok(())
}
