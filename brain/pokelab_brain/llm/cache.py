"""LLM response cache (§10.4: `var/llm_cache.db`), keyed by a hash of the
full request. Two jobs: (1) the Pokédex fast path for identical prompts
(e.g. re-asking the same capability-analysis question), and (2)
`llm-replay` mode for demo rehearsal/CI, where `fixture=1` rows are served
even with no network at all.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def cache_key(model: str, messages: list[dict[str, str]], **params: Any) -> str:
    canonical = json.dumps({"model": model, "messages": messages, "params": params}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


class LlmCache:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            " key TEXT PRIMARY KEY, model TEXT, request TEXT, response TEXT,"
            " usage TEXT, ts TEXT, fixture INTEGER DEFAULT 0)"
        )
        self._conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT response, usage FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        response, usage = row
        return {"content": response, "usage": json.loads(usage) if usage else {}}

    def put(
        self,
        key: str,
        model: str,
        request: dict[str, Any],
        response: str,
        usage: dict[str, Any],
        fixture: bool = False,
    ) -> None:
        self._conn.execute(
            "INSERT INTO cache(key, model, request, response, usage, ts, fixture) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET response = excluded.response, usage = excluded.usage",
            (
                key,
                model,
                json.dumps(request),
                response,
                json.dumps(usage),
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                int(fixture),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
