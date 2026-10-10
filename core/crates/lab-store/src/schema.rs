//! `var/lab.db` schema (§10.4 of the system architecture). labd is the only
//! writer; applied with `CREATE TABLE IF NOT EXISTS` so opening an existing
//! db is a no-op.

use rusqlite::Connection;

pub fn init(conn: &Connection) -> rusqlite::Result<()> {
    conn.pragma_update(None, "journal_mode", "WAL")?;
    conn.pragma_update(None, "synchronous", "NORMAL")?;
    conn.pragma_update(None, "foreign_keys", "ON")?;

    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            kind TEXT NOT NULL,
            v INTEGER NOT NULL DEFAULT 1,
            project TEXT,
            actor TEXT NOT NULL,
            corr TEXT,
            causation INTEGER,
            payload TEXT NOT NULL,
            display TEXT
        );
        CREATE INDEX IF NOT EXISTS ev_kind ON events(kind);
        CREATE INDEX IF NOT EXISTS ev_project ON events(project, seq);
        CREATE INDEX IF NOT EXISTS ev_corr ON events(corr);

        CREATE TABLE IF NOT EXISTS snapshots (
            name TEXT PRIMARY KEY,
            seq INTEGER NOT NULL,
            payload TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            project TEXT,
            kind TEXT NOT NULL,
            kit TEXT,
            spec TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            target TEXT NOT NULL,
            slot TEXT,
            priority INTEGER NOT NULL,
            status TEXT NOT NULL,
            submitted_ts TEXT,
            started_ts TEXT,
            ended_ts TEXT,
            final TEXT,
            error_sig TEXT,
            wall_s REAL,
            gpu_s REAL,
            source TEXT
        );
        CREATE INDEX IF NOT EXISTS jobs_hash ON jobs(config_hash, status);

        CREATE TABLE IF NOT EXISTS metrics (
            job_id TEXT,
            key TEXT,
            step INTEGER,
            value REAL,
            PRIMARY KEY(job_id, key, step)
        ) WITHOUT ROWID;

        CREATE TABLE IF NOT EXISTS artifacts (
            job_id TEXT,
            name TEXT,
            path TEXT,
            mime TEXT,
            bytes INTEGER,
            ts TEXT,
            PRIMARY KEY(job_id, name)
        );

        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        ",
    )
}
