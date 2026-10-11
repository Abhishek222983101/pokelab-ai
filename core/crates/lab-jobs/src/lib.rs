//! lab-jobs: the warm worker pool (§5.5.3). Each slot is a long-lived
//! `python -m pokelab_workers.pool_main` child process; jobs are assigned by
//! writing one JSON line to its stdin and multiplexing its stdout back to
//! whichever caller submitted that job_id. The *process* survives across
//! jobs — that's what "warm" buys (no re-import of torch, no CUDA re-init).

use std::collections::HashMap;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;

#[derive(Debug, Error)]
pub enum JobsError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("no free slot available")]
    NoFreeSlot,
}

pub type Result<T> = std::result::Result<T, JobsError>;

/// One parsed line of the worker protocol, as read from a slot's stdout.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "t")]
#[serde(rename_all = "lowercase")]
pub enum ProtocolLine {
    Ready {
        torch: bool,
        device: String,
        pid: i64,
    },
    Metric {
        job_id: String,
        step: i64,
        k: String,
        v: Option<f64>,
    },
    Log {
        job_id: String,
        msg: String,
    },
    Done {
        job_id: String,
        status: String,
        #[serde(rename = "final_")]
        final_: Option<serde_json::Value>,
        error_sig: Option<String>,
    },
}

/// `final` is a Rust keyword, so the wire field `"final"` is renamed to
/// `final_` before deserializing (only on the `done` variant).
fn parse_line(raw: &str) -> Option<ProtocolLine> {
    let mut value: serde_json::Value = serde_json::from_str(raw).ok()?;
    if value.get("t").and_then(|t| t.as_str()) == Some("done") {
        if let Some(obj) = value.as_object_mut() {
            if let Some(f) = obj.remove("final") {
                obj.insert("final_".to_string(), f);
            }
        }
    }
    serde_json::from_value(value).ok()
}

type Routes = Arc<Mutex<HashMap<String, mpsc::UnboundedSender<ProtocolLine>>>>;

struct Slot {
    child: Child,
    // `Option` so shutdown can drop it outright: tokio's `AsyncWrite::shutdown`
    // on a pipe flushes but does NOT close the fd while the value is still
    // alive, so the child never sees EOF on stdin until this is actually
    // dropped — `.shutdown().await` alone deadlocks against `child.wait()`.
    stdin: Option<tokio::process::ChildStdin>,
    busy: Arc<AtomicBool>,
    routes: Routes,
}

/// A pool of warm worker processes, one per GPU/CPU slot.
pub struct WarmPool {
    slots: Vec<Slot>,
    next_job_id: AtomicU64,
}

/// Where to find the worker entrypoint and how to run it.
pub struct PoolConfig {
    pub python: String,      // e.g. "../workers/.venv/bin/python"
    pub workers_cwd: String, // e.g. "../workers" (so `-m pokelab_workers...` resolves)
    pub n_slots: usize,
    pub device: String, // "cpu" or "cuda:0"
}

impl WarmPool {
    pub async fn spawn(cfg: PoolConfig) -> Result<Self> {
        let mut slots = Vec::with_capacity(cfg.n_slots);
        for i in 0..cfg.n_slots {
            let slot_name = format!("slot-{i}");
            let mut child = Command::new(&cfg.python)
                .arg("-I")
                .arg("-m")
                .arg("pokelab_workers.pool_main")
                .arg("--slot")
                .arg(&slot_name)
                .arg("--device")
                .arg(&cfg.device)
                .current_dir(&cfg.workers_cwd)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .kill_on_drop(true)
                .spawn()?;

            let stdin = child.stdin.take().expect("piped stdin");
            let stdout = child.stdout.take().expect("piped stdout");
            let stderr = child.stderr.take().expect("piped stderr");

            let routes: Routes = Arc::new(Mutex::new(HashMap::new()));
            let busy = Arc::new(AtomicBool::new(false));
            let routes_for_reader = routes.clone();
            let busy_for_reader = busy.clone();

            tokio::spawn(async move {
                let mut lines = BufReader::new(stdout).lines();
                loop {
                    match lines.next_line().await {
                        Ok(Some(raw)) => {
                            let Some(parsed) = parse_line(&raw) else {
                                tracing::warn!(line = %raw, "worker emitted a non-protocol line");
                                continue;
                            };
                            let job_id = match &parsed {
                                ProtocolLine::Ready { .. } => continue, // not job-scoped
                                ProtocolLine::Metric { job_id, .. } => job_id.clone(),
                                ProtocolLine::Log { job_id, .. } => job_id.clone(),
                                ProtocolLine::Done { job_id, .. } => job_id.clone(),
                            };
                            let is_done = matches!(parsed, ProtocolLine::Done { .. });
                            let sender = {
                                let mut map = routes_for_reader.lock().unwrap();
                                if is_done {
                                    map.remove(&job_id)
                                } else {
                                    map.get(&job_id).cloned()
                                }
                            };
                            if let Some(tx) = sender {
                                let _ = tx.send(parsed);
                            }
                            if is_done {
                                busy_for_reader.store(false, Ordering::SeqCst);
                            }
                        }
                        Ok(None) => break, // EOF: worker process exited
                        Err(e) => {
                            tracing::error!("worker stdout read error: {e}");
                            break;
                        }
                    }
                }
            });

            tokio::spawn(async move {
                let mut lines = BufReader::new(stderr).lines();
                while let Ok(Some(raw)) = lines.next_line().await {
                    tracing::warn!(stderr = %raw, "worker stderr");
                }
            });

            slots.push(Slot {
                child,
                stdin: Some(stdin),
                busy,
                routes,
            });
        }
        Ok(Self {
            slots,
            next_job_id: AtomicU64::new(1),
        })
    }

    /// Submit a job to the first free slot. Returns the assigned job_id and
    /// a receiver of that job's protocol lines (metric/log), ending with
    /// `Done`. The slot is marked free by the reader task itself the moment
    /// `Done` is parsed — callers don't need to signal anything back.
    pub async fn submit(
        &mut self,
        kit: &str,
        config: serde_json::Value,
    ) -> Result<(String, mpsc::UnboundedReceiver<ProtocolLine>)> {
        let slot = self
            .slots
            .iter_mut()
            .find(|s| !s.busy.load(Ordering::SeqCst))
            .ok_or(JobsError::NoFreeSlot)?;

        let job_id = format!("job-{}", self.next_job_id.fetch_add(1, Ordering::SeqCst));
        let (tx, rx) = mpsc::unbounded_channel();
        slot.routes.lock().unwrap().insert(job_id.clone(), tx);
        slot.busy.store(true, Ordering::SeqCst);

        let line = serde_json::json!({"t": "job", "job_id": job_id, "kit": kit, "config": config});
        let mut payload = serde_json::to_string(&line).unwrap();
        payload.push('\n');
        let stdin = slot
            .stdin
            .as_mut()
            .expect("slot stdin only taken during shutdown, after which it is never submitted to again");
        stdin.write_all(payload.as_bytes()).await?;

        Ok((job_id, rx))
    }

    /// Convenience for tests / non-streaming callers: submit one job and
    /// collect every protocol line until (and including) `Done`.
    pub async fn submit_and_collect(
        &mut self,
        kit: &str,
        config: serde_json::Value,
    ) -> Result<(String, Vec<ProtocolLine>)> {
        let (job_id, mut rx) = self.submit(kit, config).await?;
        let mut lines = Vec::new();
        while let Some(line) = rx.recv().await {
            let done = matches!(line, ProtocolLine::Done { .. });
            lines.push(line);
            if done {
                break;
            }
        }
        Ok((job_id, lines))
    }

    /// Sends `{"t":"stop","job_id":...}` to whichever slot is actually
    /// running this job. Returns `false` if no slot currently routes
    /// this job_id (already finished, or never existed) — not an error,
    /// just nothing to do. The worker side applies this via a dedicated
    /// reader thread so it takes effect immediately, not only between
    /// jobs (see workers/pokelab_workers/pool_main.py's docstring on the
    /// bug this fixed).
    pub async fn stop_job(&mut self, job_id: &str) -> Result<bool> {
        for slot in &mut self.slots {
            let has_job = slot.routes.lock().unwrap().contains_key(job_id);
            if has_job {
                let line = serde_json::json!({"t": "stop", "job_id": job_id});
                let mut payload = serde_json::to_string(&line).unwrap();
                payload.push('\n');
                if let Some(stdin) = slot.stdin.as_mut() {
                    stdin.write_all(payload.as_bytes()).await?;
                }
                return Ok(true);
            }
        }
        Ok(false)
    }

    pub fn n_slots(&self) -> usize {
        self.slots.len()
    }

    pub fn free_slots(&self) -> usize {
        self.slots
            .iter()
            .filter(|s| !s.busy.load(Ordering::SeqCst))
            .count()
    }

    /// Clean shutdown: close stdin on every slot so pool_main's
    /// `for line in sys.stdin` loop ends and the process exits on its own.
    pub async fn shutdown(mut self) {
        for slot in &mut self.slots {
            if let Some(mut stdin) = slot.stdin.take() {
                let _ = stdin.shutdown().await; // flush, then...
                drop(stdin); // ...actually close the fd, so the child sees EOF
            }
        }
        for slot in &mut self.slots {
            let _ = slot.child.wait().await;
        }
    }
}
