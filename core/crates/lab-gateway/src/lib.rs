//! lab-gateway: axum routes, WS hub, cmd intake, static serving, auth/pairing.
//! Ships `/api/health`, `/api/events/since` (poll fallback), the phone
//! pairing flow (§5.8), the client WS fan-out (`/api/ws`) and the internal
//! brain socket (`/internal/brain`, §5.4.3). Static file serving is still
//! open (see docs/PROGRESS.md P1.2).

use std::sync::Arc;

use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use lab_jobs::WarmPool;
use lab_store::Store;
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;
use tower_http::services::ServeDir;

pub mod auth;
pub mod hub;
pub mod ws;

use auth::{PairingStore, Role};
use hub::Hub;

#[derive(Clone)]
pub struct AppState {
    pub hub: Arc<Hub>,
    pub pairing: Arc<PairingStore>,
    pub brain_secret: Arc<[u8]>,
    pub warm_pool: Option<Arc<Mutex<WarmPool>>>,
}

pub fn router(store: Arc<Store>, brain_secret: Vec<u8>, warm_pool: Option<WarmPool>) -> Router {
    router_with_web(store, brain_secret, warm_pool, None)
}

/// Same as `router`, plus serving the static-exported web app (§4.4, §8.2)
/// from `web_dir` (e.g. `../web/out`) for any path the API routes above
/// don't claim. `None` means "no web build yet" — the API still works,
/// just with no UI behind it (useful for pure backend tests).
pub fn router_with_web(
    store: Arc<Store>,
    brain_secret: Vec<u8>,
    warm_pool: Option<WarmPool>,
    web_dir: Option<std::path::PathBuf>,
) -> Router {
    let state = AppState {
        hub: Arc::new(Hub::new(store)),
        pairing: Arc::new(PairingStore::new()),
        brain_secret: brain_secret.into(),
        warm_pool: warm_pool.map(|p| Arc::new(Mutex::new(p))),
    };

    let mut router = Router::new()
        .route("/api/health", get(health))
        .route("/api/telemetry", get(telemetry))
        .route("/api/events/since", get(events_since))
        .route("/api/pair/issue", post(pair_issue))
        .route("/api/pair/claim", post(pair_claim))
        .route("/api/ws", get(ws::client_ws))
        .route("/internal/brain", get(ws::brain_ws))
        .with_state(state);

    if let Some(dir) = web_dir {
        // fallback_service: any path none of the routes above matched
        // falls through to the static export (including nested pages,
        // since each is its own prerendered .html under `out/`).
        router = router.fallback_service(ServeDir::new(dir));
    }

    router
}

#[derive(Serialize)]
struct Health {
    status: &'static str,
    latest_seq: i64,
}

async fn health(State(state): State<AppState>) -> Json<Health> {
    let latest_seq = state.hub.store().latest_seq().unwrap_or(-1);
    Json(Health {
        status: "ok",
        latest_seq,
    })
}

/// Live GPU numbers for the HUD (§5.7). `gpu: null` means nvidia-smi gave nothing (no GPU / not
/// installed): the UI shows "—", never a made-up figure.
#[derive(Serialize)]
struct Telemetry {
    gpu: Option<GpuJson>,
}

#[derive(Serialize)]
struct GpuJson {
    name: Option<String>,
    util_pct: Option<f64>,
    mem_used_mib: Option<f64>,
    mem_total_mib: Option<f64>,
    power_w: Option<f64>,
    temp_c: Option<f64>,
}

async fn telemetry() -> impl axum::response::IntoResponse {
    // read-only GPU numbers: allow the Vercel-hosted desk to fetch them cross-origin
    ([(axum::http::header::ACCESS_CONTROL_ALLOW_ORIGIN, "*")], telemetry_json().await)
}

async fn telemetry_json() -> Json<Telemetry> {
    let gpu = tokio::task::spawn_blocking(lab_telemetry::sample_gpu)
        .await
        .ok()
        .flatten()
        .map(|g| GpuJson {
            name: g.name,
            util_pct: g.util_pct,
            mem_used_mib: g.mem_used_mib,
            mem_total_mib: g.mem_total_mib,
            power_w: g.power_w,
            temp_c: g.temp_c,
        });
    Json(Telemetry { gpu })
}

#[derive(Deserialize)]
struct SinceQuery {
    after: Option<i64>,
    project: Option<String>,
}

async fn events_since(
    State(state): State<AppState>,
    Query(q): Query<SinceQuery>,
) -> Json<Vec<lab_store::Event>> {
    let events = state
        .hub
        .store()
        .since(q.after.unwrap_or(0), q.project.as_deref())
        .unwrap_or_default();
    Json(events)
}

#[derive(Deserialize)]
struct PairIssueRequest {
    role: String, // "phone" or "view" — desk never needs a pairing code
}

#[derive(Serialize)]
struct PairIssueResponse {
    code: String,
    expires_in_s: u64,
}

async fn pair_issue(
    State(state): State<AppState>,
    Json(req): Json<PairIssueRequest>,
) -> std::result::Result<Json<PairIssueResponse>, StatusCode> {
    let role = match req.role.as_str() {
        "phone" => Role::Phone,
        "view" => Role::View,
        _ => return Err(StatusCode::BAD_REQUEST),
    };
    let code = state.pairing.issue(role);
    Ok(Json(PairIssueResponse {
        code,
        expires_in_s: 5 * 60,
    }))
}

#[derive(Deserialize)]
struct PairClaimRequest {
    code: String,
    device_id: String,
}

#[derive(Serialize)]
struct PairClaimResponse {
    token: String,
    role: String,
}

async fn pair_claim(
    State(state): State<AppState>,
    Json(req): Json<PairClaimRequest>,
) -> std::result::Result<Json<PairClaimResponse>, StatusCode> {
    let role = state
        .pairing
        .claim(&req.code)
        .ok_or(StatusCode::UNAUTHORIZED)?;
    let token = auth::issue_token(&state.brain_secret, &req.device_id, role, 24);
    Ok(Json(PairClaimResponse {
        token,
        role: role.as_str().to_string(),
    }))
}
