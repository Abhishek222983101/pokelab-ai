//! lab-gateway: axum routes, WS hub, cmd intake, static serving, auth/pairing.
//! P1.2 ships `/api/health` and `/api/events/since` (poll fallback); the
//! WebSocket hub and auth/pairing land with P1.2's remaining work and P1.6.

use std::sync::Arc;

use axum::extract::{Query, State};
use axum::routing::get;
use axum::{Json, Router};
use lab_store::Store;
use serde::{Deserialize, Serialize};

#[derive(Clone)]
pub struct AppState {
    pub store: Arc<Store>,
}

pub fn router(store: Arc<Store>) -> Router {
    Router::new()
        .route("/api/health", get(health))
        .route("/api/events/since", get(events_since))
        .with_state(AppState { store })
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
