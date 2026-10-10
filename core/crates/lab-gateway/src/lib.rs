//! lab-gateway: axum routes, WS hub, cmd intake, static serving, auth/pairing.
//! Ships `/api/health`, `/api/events/since` (poll fallback) and the phone
//! pairing flow (§5.8). The WebSocket hub and static file serving are still
//! open (see docs/PROGRESS.md P1.2).

use std::sync::Arc;

use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use lab_store::Store;
use serde::{Deserialize, Serialize};

pub mod auth;

use auth::{PairingStore, Role};

#[derive(Clone)]
pub struct AppState {
    pub store: Arc<Store>,
    pub pairing: Arc<PairingStore>,
    pub brain_secret: Arc<[u8]>,
}

pub fn router(store: Arc<Store>, brain_secret: Vec<u8>) -> Router {
    Router::new()
        .route("/api/health", get(health))
        .route("/api/events/since", get(events_since))
        .route("/api/pair/issue", post(pair_issue))
        .route("/api/pair/claim", post(pair_claim))
        .with_state(AppState {
            store,
            pairing: Arc::new(PairingStore::new()),
            brain_secret: brain_secret.into(),
        })
}

#[derive(Serialize)]
struct Health {
    status: &'static str,
    latest_seq: i64,
}

async fn health(State(state): State<AppState>) -> Json<Health> {
    let latest_seq = state.store.latest_seq().unwrap_or(-1);
    Json(Health {
        status: "ok",
        latest_seq,
    })
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
        .store
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
