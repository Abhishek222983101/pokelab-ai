//! WebSocket endpoints (§5.4). `/api/ws` is the client fan-out (desk,
//! phone, view); `/internal/brain` is the single trusted connection the
//! Python brain uses to publish events and submit jobs.

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::State;
use axum::http::{HeaderMap, StatusCode};
use axum::response::IntoResponse;
use futures_util::{SinkExt, StreamExt};
use lab_jobs::ProtocolLine;
use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;

use crate::AppState;

// ---------- client WS (/api/ws) ----------

#[derive(Deserialize)]
#[serde(tag = "type")]
enum ClientMsg {
    #[serde(rename = "hello")]
    Hello { since: i64 },
}

#[derive(Serialize)]
#[serde(tag = "type")]
enum ServerMsg<'a> {
    #[serde(rename = "event")]
    Event { e: &'a lab_store::Event },
    #[serde(rename = "resync")]
    Resync { since: i64 },
}

pub async fn client_ws(ws: WebSocketUpgrade, State(state): State<AppState>) -> impl IntoResponse {
    ws.on_upgrade(move |socket| client_ws_loop(socket, state))
}

async fn client_ws_loop(mut socket: WebSocket, state: AppState) {
    // Wait for `hello` (bounded — a client that never says hello just times
    // out its own connection; nothing to clean up on our side beyond drop).
    let since = loop {
        match socket.recv().await {
            Some(Ok(Message::Text(text))) => match serde_json::from_str::<ClientMsg>(&text) {
                Ok(ClientMsg::Hello { since }) => break since,
                Err(_) => continue, // ignore until we get a valid hello
            },
            Some(Ok(_)) => continue,
            _ => return, // closed before saying hello
        }
    };

    // Fan-out order (§5.4.2): subscribe FIRST, then replay — so no event
    // committed after the subscribe can fall into the gap before replay.
    let mut rx = state.hub.subscribe();
    let backlog = state.hub.store().since(since, None).unwrap_or_default();
    let mut last_sent = since;
    for e in &backlog {
        last_sent = e.seq;
        if send_event(&mut socket, e).await.is_err() {
            return;
        }
    }

    loop {
        match rx.recv().await {
            Ok(e) => {
                if e.seq <= last_sent {
                    continue; // already sent via replay
                }
                last_sent = e.seq;
                if send_event(&mut socket, &e).await.is_err() {
                    return;
                }
            }
            Err(broadcast::error::RecvError::Lagged(_)) => {
                let msg = ServerMsg::Resync { since: last_sent };
                let text = serde_json::to_string(&msg).unwrap();
                if socket.send(Message::Text(text.into())).await.is_err() {
                    return;
                }
                let backlog = state.hub.store().since(last_sent, None).unwrap_or_default();
                for e in &backlog {
                    last_sent = e.seq;
                    if send_event(&mut socket, e).await.is_err() {
                        return;
                    }
                }
            }
            Err(broadcast::error::RecvError::Closed) => return,
        }
    }
}

async fn send_event(socket: &mut WebSocket, e: &lab_store::Event) -> Result<(), axum::Error> {
    let msg = ServerMsg::Event { e };
    let text = serde_json::to_string(&msg).unwrap();
    socket.send(Message::Text(text.into())).await
}

// ---------- internal brain WS (/internal/brain) ----------

#[derive(Deserialize)]
#[serde(tag = "type")]
enum BrainMsg {
    #[serde(rename = "publish")]
    Publish {
        events: Vec<lab_store::NewEvent>,
        req: String,
    },
    #[serde(rename = "job_submit")]
    JobSubmit {
        req: String,
        kit: String,
        config: serde_json::Value,
        project: Option<String>,
    },
    #[serde(rename = "subscribe")]
    Subscribe { since: i64 },
}

#[derive(Serialize)]
#[serde(tag = "type")]
enum LabdMsg<'a> {
    #[serde(rename = "published")]
    Published { req: String, seqs: Vec<i64> },
    #[serde(rename = "job_accepted")]
    JobAccepted { req: String, job_id: String },
    #[serde(rename = "job_rejected")]
    JobRejected { req: String, reason: String },
    #[serde(rename = "event")]
    Event { e: &'a lab_store::Event },
}

/// Authorization: Bearer $LABD_BRAIN_SECRET — checked before upgrading, so
/// an unauthenticated caller gets a plain 401, never a WS handshake.
pub async fn brain_ws(
    ws: WebSocketUpgrade,
    headers: HeaderMap,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, StatusCode> {
    let auth = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let expected = format!("Bearer {}", String::from_utf8_lossy(&state.brain_secret));
    if auth != expected {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(ws.on_upgrade(move |socket| brain_ws_loop(socket, state)))
}

async fn brain_ws_loop(socket: WebSocket, state: AppState) {
    let (mut tx_sock, mut rx_sock) = socket.split();
    let mut hub_rx: Option<broadcast::Receiver<lab_store::Event>> = None;

    loop {
        tokio::select! {
            incoming = rx_sock.next() => {
                let Some(Ok(Message::Text(text))) = incoming else { return };
                let Ok(cmd) = serde_json::from_str::<BrainMsg>(&text) else {
                    tracing::warn!(line = %text, "brain sent an unparseable message");
                    continue;
                };
                match cmd {
                    BrainMsg::Publish { events, req } => {
                        let mut seqs = Vec::with_capacity(events.len());
                        for ev in events {
                            match state.hub.publish(ev) {
                                Ok(e) => seqs.push(e.seq),
                                Err(e) => tracing::error!("publish failed: {e}"),
                            }
                        }
                        let reply = LabdMsg::Published { req, seqs };
                        send_to_brain(&mut tx_sock, &reply).await;
                    }
                    BrainMsg::Subscribe { since } => {
                        hub_rx = Some(state.hub.subscribe());
                        let backlog = state.hub.store().since(since, None).unwrap_or_default();
                        for e in &backlog {
                            send_to_brain(&mut tx_sock, &LabdMsg::Event { e }).await;
                        }
                    }
                    BrainMsg::JobSubmit { req, kit, config, project } => {
                        handle_job_submit(&state, &mut tx_sock, req, kit, config, project).await;
                    }
                }
            }
            maybe_event = recv_optional(&mut hub_rx) => {
                if let Some(e) = maybe_event {
                    send_to_brain(&mut tx_sock, &LabdMsg::Event { e: &e }).await;
                }
            }
        }
    }
}

async fn recv_optional(
    rx: &mut Option<broadcast::Receiver<lab_store::Event>>,
) -> Option<lab_store::Event> {
    match rx {
        None => {
            // never resolves — just keeps the select! arm pending until a
            // subscription exists
            std::future::pending::<()>().await;
            None
        }
        Some(r) => r.recv().await.ok(),
    }
}

async fn handle_job_submit(
    state: &AppState,
    tx_sock: &mut (impl SinkExt<Message, Error = axum::Error> + Unpin),
    req: String,
    kit: String,
    config: serde_json::Value,
    project: Option<String>,
) {
    let Some(pool) = &state.warm_pool else {
        let reply = LabdMsg::JobRejected {
            req,
            reason: "no warm pool configured on this labd instance".to_string(),
        };
        send_to_brain(tx_sock, &reply).await;
        return;
    };

    let mut pool = pool.lock().await;
    let submission = pool.submit(&kit, config.clone()).await;
    match submission {
        Ok((job_id, mut rx)) => {
            let reply = LabdMsg::JobAccepted {
                req,
                job_id: job_id.clone(),
            };
            send_to_brain(tx_sock, &reply).await;

            let hub = state.hub.clone();
            let project_for_task = project.clone();
            let job_id_for_task = job_id.clone();
            // stream this job's protocol lines into real events, independent
            // of the main select! loop above (so a second job can be
            // submitted while this one is still running on another slot).
            tokio::spawn(async move {
                while let Some(line) = rx.recv().await {
                    let (kind, payload, done) = match &line {
                        ProtocolLine::Metric { step, k, v, .. } => (
                            "job.metric",
                            serde_json::json!({"job_id": job_id_for_task, "step": step, "k": k, "v": v}),
                            false,
                        ),
                        ProtocolLine::Log { msg, .. } => (
                            "job.log",
                            serde_json::json!({"job_id": job_id_for_task, "msg": msg}),
                            false,
                        ),
                        ProtocolLine::Done { status, final_, error_sig, .. } => (
                            "job.done",
                            serde_json::json!({
                                "job_id": job_id_for_task, "status": status,
                                "final": final_, "error_sig": error_sig
                            }),
                            true,
                        ),
                        ProtocolLine::Ready { .. } => continue,
                    };
                    let _ = hub.publish(lab_store::NewEvent {
                        kind: kind.to_string(),
                        v: 1,
                        project: project_for_task.clone(),
                        actor: "labd".to_string(),
                        corr: None,
                        causation: None,
                        payload,
                        display: None,
                    });
                    if done {
                        break;
                    }
                }
            });
        }
        Err(e) => {
            let reply = LabdMsg::JobRejected {
                req,
                reason: e.to_string(),
            };
            send_to_brain(tx_sock, &reply).await;
        }
    }
}

async fn send_to_brain(
    tx_sock: &mut (impl SinkExt<Message, Error = axum::Error> + Unpin),
    msg: &LabdMsg<'_>,
) {
    let text = serde_json::to_string(msg).unwrap();
    let _ = tx_sock.send(Message::Text(text.into())).await;
}
