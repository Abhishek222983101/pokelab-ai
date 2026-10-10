//! labd: the PokéLab core daemon. Boots the event store and serves the
//! gateway's HTTP/WS API. `labd doctor` runs the preflight checks (§11.2);
//! `labd replay <db>` serves a recorded session read-only (§4.6).

mod doctor;

use std::sync::Arc;

use anyhow::Context;
use clap::{Parser, Subcommand};

#[derive(Parser)]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Start labd (default if no subcommand is given).
    Up,
    /// Run the preflight checks and exit — GPU, power, disk, assets,
    /// datasets, the workers venv, required env vars (§11.2, §4.6).
    Doctor,
    /// Serve a recorded session's db read-only (REPLAY mode, §11.2 last row).
    Replay { db_path: std::path::PathBuf },
}

fn default_port() -> u16 {
    7700
}

fn default_db_path() -> std::path::PathBuf {
    std::path::PathBuf::from("../var/lab.db")
}

/// Starts the GPU/CPU warm worker pool (§5.5.3) if `LABD_WORKERS_PYTHON` is
/// set — on a box without the workers venv built yet, labd still boots
/// (job_submit just gets rejected with a clear reason, see ws.rs) rather
/// than refusing to start.
async fn spawn_warm_pool_if_configured() -> Option<lab_jobs::WarmPool> {
    let python = std::env::var("LABD_WORKERS_PYTHON").ok()?;
    let workers_cwd = std::env::var("LABD_WORKERS_CWD").unwrap_or_else(|_| "../workers".to_string());
    let device = std::env::var("LABD_WORKER_DEVICE").unwrap_or_else(|_| "cpu".to_string());
    let n_slots: usize = std::env::var("LABD_POOL_SIZE")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);

    // §11.6: workers log W&B offline into var/wandb/ — this is the only
    // place that path is set; WANDB_API_KEY is never exported to children.
    if std::env::var("WANDB_DIR").is_err() {
        std::env::set_var("WANDB_DIR", "../var/wandb");
        std::env::set_var("WANDB_MODE", "offline");
    }

    let cfg = lab_jobs::PoolConfig {
        python,
        workers_cwd,
        n_slots,
        device,
    };
    match lab_jobs::WarmPool::spawn(cfg).await {
        Ok(pool) => {
            tracing::info!(slots = pool.n_slots(), "warm worker pool started");
            Some(pool)
        }
        Err(e) => {
            tracing::error!("failed to start warm worker pool: {e}");
            None
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    let cli = Cli::parse();

    match cli.command.unwrap_or(Command::Up) {
        Command::Doctor => run_doctor(),
        Command::Up => run_up(db_path_from_env(), false).await,
        Command::Replay { db_path } => run_up(db_path, true).await,
    }
}

/// `LABD_DB_PATH` if set, else the default. Lost in an earlier refactor
/// (the CLI dispatch called `default_db_path()` directly) — every test
/// that set `LABD_DB_PATH` to an isolated tmp file was silently writing
/// to and reading from the shared `../var/lab.db` instead, replaying
/// *other tests'* old jobs. Caught via the vertical-slice test returning
/// a stale smoke-kit result for a job actually submitted as `grokking`.
fn db_path_from_env() -> std::path::PathBuf {
    std::env::var("LABD_DB_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| default_db_path())
}

/// `labd doctor` — exits non-zero if any check fails, so `just doctor` in CI
/// or before a demo is a real gate, not just a printout.
fn run_doctor() -> anyhow::Result<()> {
    let results = doctor::run();
    let mut all_ok = true;
    for r in &results {
        let mark = if r.ok { "✅" } else { "❌" };
        println!("{mark} {:<14} {}", r.name, r.detail);
        all_ok &= r.ok;
    }
    if all_ok {
        println!("\nall checks passed");
        Ok(())
    } else {
        anyhow::bail!("one or more doctor checks failed — see above")
    }
}

async fn run_up(db_path: std::path::PathBuf, read_only: bool) -> anyhow::Result<()> {
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).context("creating var/ for lab.db")?;
    }

    let store = Arc::new(lab_store::Store::open(&db_path).context("opening lab.db")?);
    tracing::info!(?db_path, read_only, "lab-store opened");

    let port: u16 = std::env::var("LABD_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or_else(default_port);

    let brain_secret = std::env::var("LABD_BRAIN_SECRET")
        .unwrap_or_else(|_| "dev-only-insecure-secret-set-LABD_BRAIN_SECRET".to_string())
        .into_bytes();

    // REPLAY mode never runs real jobs — a recorded session is played back
    // exactly as events in the db, not re-executed (§11.2 last row).
    let warm_pool = if read_only {
        None
    } else {
        spawn_warm_pool_if_configured().await
    };

    let app = lab_gateway::router(store, brain_secret, warm_pool);
    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .with_context(|| format!("binding {addr}"))?;
    tracing::info!(%addr, "labd listening");
    axum::serve(listener, app).await.context("serving")?;
    Ok(())
}
