//! lab-store: the event store. labd is the single writer. SQLite in WAL mode.
//! Everything the game shows traces back to a row in `events` — this crate is
//! the one place allowed to write one.

mod schema;

use std::path::Path;
use std::sync::mpsc;
use std::thread;

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum StoreError {
    #[error("sqlite error: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("writer thread is gone")]
    WriterGone,
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, StoreError>;

/// A row as it will be appended to `events`. `seq` is assigned by the writer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewEvent {
    pub kind: String,
    #[serde(default = "default_version")]
    pub v: i64,
    pub project: Option<String>,
    pub actor: String,
    pub corr: Option<String>,
    pub causation: Option<i64>,
    pub payload: serde_json::Value,
    pub display: Option<serde_json::Value>,
}

fn default_version() -> i64 {
    1
}

/// A row as read back from `events`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    pub seq: i64,
    pub ts: String,
    pub kind: String,
    pub v: i64,
    pub project: Option<String>,
    pub actor: String,
    pub corr: Option<String>,
    pub causation: Option<i64>,
    pub payload: serde_json::Value,
    pub display: Option<serde_json::Value>,
}

enum WriteCmd {
    Append {
        event: NewEvent,
        reply: mpsc::Sender<Result<Event>>,
    },
}

/// Handle to the store. Cloneable; every clone shares the one writer thread
/// (and therefore the one `events.seq` ordering) via an mpsc channel.
#[derive(Clone)]
pub struct Store {
    tx: mpsc::Sender<WriteCmd>,
    read_path: std::path::PathBuf,
}

impl Store {
    /// Open (creating if needed) the event store at `path` and start its
    /// single writer thread.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref().to_path_buf();
        let conn = Connection::open(&path)?;
        schema::init(&conn)?;
        drop(conn);

        let (tx, rx) = mpsc::channel::<WriteCmd>();
        let writer_path = path.clone();
        thread::spawn(move || writer_loop(writer_path, rx));

        Ok(Self {
            tx,
            read_path: path,
        })
    }

    /// Append one event. Blocks the calling thread until the writer has
    /// committed it (group-commit batches this internally in labd's gateway
    /// layer — this crate just guarantees one writer, one order).
    pub fn append(&self, event: NewEvent) -> Result<Event> {
        let (reply_tx, reply_rx) = mpsc::channel();
        self.tx
            .send(WriteCmd::Append {
                event,
                reply: reply_tx,
            })
            .map_err(|_| StoreError::WriterGone)?;
        reply_rx.recv().map_err(|_| StoreError::WriterGone)?
    }

    /// Open a fresh read-only connection. Safe to call from any thread;
    /// SQLite WAL allows concurrent readers alongside the one writer.
    fn read_conn(&self) -> Result<Connection> {
        let conn = Connection::open(&self.read_path)?;
        conn.pragma_update(None, "query_only", true)?;
        Ok(conn)
    }

    /// All events with `seq > after`, optionally filtered to one project,
    /// in seq order. Used for catch-up on reconnect.
    pub fn since(&self, after: i64, project: Option<&str>) -> Result<Vec<Event>> {
        let conn = self.read_conn()?;
        let mut rows = Vec::new();
        let mut push = |r: &rusqlite::Row| -> rusqlite::Result<()> {
            rows.push(row_to_event(r)?);
            Ok(())
        };
        if let Some(project) = project {
            let mut stmt = conn.prepare(
                "SELECT seq, ts, kind, v, project, actor, corr, causation, payload, display \
                 FROM events WHERE seq > ?1 AND project = ?2 ORDER BY seq ASC",
            )?;
            let mut r = stmt.query(params![after, project])?;
            while let Some(row) = r.next()? {
                push(row)?;
            }
        } else {
            let mut stmt = conn.prepare(
                "SELECT seq, ts, kind, v, project, actor, corr, causation, payload, display \
                 FROM events WHERE seq > ?1 ORDER BY seq ASC",
            )?;
            let mut r = stmt.query(params![after])?;
            while let Some(row) = r.next()? {
                push(row)?;
            }
        }
        Ok(rows)
    }

    pub fn latest_seq(&self) -> Result<i64> {
        let conn = self.read_conn()?;
        let seq: Option<i64> = conn
            .query_row("SELECT MAX(seq) FROM events", [], |r| r.get(0))
            .optional()?
            .flatten();
        Ok(seq.unwrap_or(0))
    }

    pub fn save_snapshot(&self, name: &str, seq: i64, payload: &serde_json::Value) -> Result<()> {
        let conn = self.read_conn_writable_kv()?;
        conn.execute(
            "INSERT INTO snapshots(name, seq, payload) VALUES (?1, ?2, ?3) \
             ON CONFLICT(name) DO UPDATE SET seq = excluded.seq, payload = excluded.payload",
            params![name, seq, payload.to_string()],
        )?;
        Ok(())
    }

    pub fn load_snapshot(&self, name: &str) -> Result<Option<(i64, serde_json::Value)>> {
        let conn = self.read_conn()?;
        let row: Option<(i64, String)> = conn
            .query_row(
                "SELECT seq, payload FROM snapshots WHERE name = ?1",
                params![name],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .optional()?;
        Ok(match row {
            Some((seq, payload)) => Some((seq, serde_json::from_str(&payload)?)),
            None => None,
        })
    }

    // snapshots/kv are low-frequency; a short-lived writable connection is
    // fine for them (SQLite serialises writers, and WAL lets this interleave
    // with the event writer thread without blocking readers).
    fn read_conn_writable_kv(&self) -> Result<Connection> {
        Connection::open(&self.read_path).map_err(StoreError::from)
    }
}

fn row_to_event(r: &rusqlite::Row) -> rusqlite::Result<Event> {
    let payload: String = r.get(8)?;
    let display: Option<String> = r.get(9)?;
    Ok(Event {
        seq: r.get(0)?,
        ts: r.get(1)?,
        kind: r.get(2)?,
        v: r.get(3)?,
        project: r.get(4)?,
        actor: r.get(5)?,
        corr: r.get(6)?,
        causation: r.get(7)?,
        payload: serde_json::from_str(&payload).unwrap_or(serde_json::Value::Null),
        display: display.and_then(|d| serde_json::from_str(&d).ok()),
    })
}

fn writer_loop(path: std::path::PathBuf, rx: mpsc::Receiver<WriteCmd>) {
    let conn = match Connection::open(&path) {
        Ok(c) => c,
        Err(e) => {
            tracing::error!("lab-store writer could not open {path:?}: {e}");
            return;
        }
    };
    if let Err(e) = schema::init(&conn) {
        tracing::error!("lab-store writer could not init schema: {e}");
        return;
    }

    while let Ok(cmd) = rx.recv() {
        match cmd {
            WriteCmd::Append { event, reply } => {
                let result = append_one(&conn, &event);
                let _ = reply.send(result);
            }
        }
    }
}

fn append_one(conn: &Connection, event: &NewEvent) -> Result<Event> {
    let payload = serde_json::to_string(&event.payload)?;
    let display = event
        .display
        .as_ref()
        .map(serde_json::to_string)
        .transpose()?;
    conn.execute(
        "INSERT INTO events (ts, kind, v, project, actor, corr, causation, payload, display) \
         VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            event.kind,
            event.v,
            event.project,
            event.actor,
            event.corr,
            event.causation,
            payload,
            display,
        ],
    )?;
    let seq = conn.last_insert_rowid();
    let conn2 = conn; // same connection, read our own write back for the ts
    let row = conn2.query_row(
        "SELECT seq, ts, kind, v, project, actor, corr, causation, payload, display \
         FROM events WHERE seq = ?1",
        params![seq],
        row_to_event,
    )?;
    Ok(row)
}
