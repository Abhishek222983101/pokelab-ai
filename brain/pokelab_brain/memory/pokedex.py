"""Memory — the Pokédex (§6.7). `var/brain.db`'s `lessons` and `fixes`
tables (§10.4). The one rule the spec is explicit about: **a lesson is
saved only with a link to the run(s) that support it** — memory never
stores an unsupported claim. `save_lesson` enforces that in code, not by
convention.

Retrieval here is exact-match (fixes) and keyword-overlap ranking
(lessons) — a real, working, honest stand-in for the embedding-kNN
retrieval the full spec calls for; fastembed isn't wired up yet (tracked
in docs/PROGRESS.md), so this never pretends to do semantic search it
isn't doing.
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Lesson:
    id: str
    text: str
    kind: str
    evidence: list[str]
    created_seq: int | None


@dataclass
class Fix:
    signature: str
    error_class: str
    fix: str
    success: int
    failure: int
    source_job: str | None


_WORD_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


class Pokedex:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS lessons ("
            " id TEXT PRIMARY KEY, text TEXT, kind TEXT, evidence TEXT, created_seq INTEGER)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS fixes ("
            " signature TEXT PRIMARY KEY, class TEXT, fix TEXT,"
            " success INTEGER DEFAULT 0, failure INTEGER DEFAULT 0, source_job TEXT)"
        )
        self._conn.commit()

    # ---------- lessons ----------

    def save_lesson(self, text: str, kind: str, evidence: list[str], created_seq: int | None = None) -> str:
        if not evidence:
            raise ValueError(
                "a lesson must cite the run(s) that support it — §6.7's rule against "
                "unsupported claims in shared memory (the AgentRxiv hallucination problem)"
            )
        lesson_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO lessons(id, text, kind, evidence, created_seq) VALUES (?, ?, ?, ?, ?)",
            (lesson_id, text, kind, ",".join(evidence), created_seq),
        )
        self._conn.commit()
        return lesson_id

    def search_lessons(self, query: str, kind: str | None = None, k: int = 5) -> list[Lesson]:
        query_tokens = _tokenize(query)
        sql = "SELECT id, text, kind, evidence, created_seq FROM lessons"
        params: tuple = ()
        if kind is not None:
            sql += " WHERE kind = ?"
            params = (kind,)
        rows = self._conn.execute(sql, params).fetchall()

        scored = []
        for lesson_id, text, lesson_kind, evidence, created_seq in rows:
            overlap = len(query_tokens & _tokenize(text))
            if overlap > 0:
                scored.append((overlap, Lesson(lesson_id, text, lesson_kind, evidence.split(","), created_seq)))
        scored.sort(key=lambda t: -t[0])
        return [lesson for _, lesson in scored[:k]]

    # ---------- fixes ----------

    def lookup_fix(self, signature: str) -> Fix | None:
        row = self._conn.execute(
            "SELECT signature, class, fix, success, failure, source_job FROM fixes WHERE signature = ?",
            (signature,),
        ).fetchone()
        return Fix(*row) if row else None

    def record_fix(self, signature: str, error_class: str, fix: str, succeeded: bool, source_job: str | None = None) -> None:
        existing = self.lookup_fix(signature)
        if existing is None:
            self._conn.execute(
                "INSERT INTO fixes(signature, class, fix, success, failure, source_job) VALUES (?, ?, ?, ?, ?, ?)",
                (signature, error_class, fix, 1 if succeeded else 0, 0 if succeeded else 1, source_job),
            )
        else:
            col = "success" if succeeded else "failure"
            self._conn.execute(f"UPDATE fixes SET {col} = {col} + 1, fix = ? WHERE signature = ?", (fix, signature))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
