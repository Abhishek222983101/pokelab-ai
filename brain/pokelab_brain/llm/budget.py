"""Per-provider daily token budget (§10.4 brain.db: `budget` table).
Elevate resets at 00:00 UTC (05:30 IST) — tracked by calendar day in UTC,
matching the gateway exactly rather than this machine's local clock.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BudgetTracker:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS budget ("
            " day TEXT, provider TEXT, tokens INTEGER, requests INTEGER,"
            " PRIMARY KEY(day, provider))"
        )
        self._conn.commit()

    def record(self, provider: str, tokens: int) -> None:
        day = _today_utc()
        self._conn.execute(
            "INSERT INTO budget(day, provider, tokens, requests) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(day, provider) DO UPDATE SET "
            "tokens = tokens + excluded.tokens, requests = requests + 1",
            (day, provider, tokens),
        )
        self._conn.commit()

    def used_today(self, provider: str) -> tuple[int, int]:
        """Returns (tokens_used, requests_made) for `provider` today (UTC)."""
        row = self._conn.execute(
            "SELECT tokens, requests FROM budget WHERE day = ? AND provider = ?",
            (_today_utc(), provider),
        ).fetchone()
        return (row[0], row[1]) if row else (0, 0)

    def would_exceed(self, provider: str, daily_limit: int, estimated_tokens: int) -> bool:
        used, _ = self.used_today(provider)
        return used + estimated_tokens > daily_limit

    def close(self) -> None:
        self._conn.close()
