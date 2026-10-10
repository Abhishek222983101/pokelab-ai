"""Discovery (§6.6.3): `discover.arxiv` — find papers related to a
project goal. Real arXiv API calls (rate-limited to the library's own
default, 1 request / 3s per `arxiv` 4.0.1's `Client`), with a simple
sqlite cache so a repeated query never re-hits the network (and still
works offline once warmed — §11.3's offline-first rule applies here too).
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import arxiv


@dataclass
class ArxivResult:
    arxiv_id: str
    title: str
    summary: str
    pdf_url: str
    published: str


class ArxivCache:
    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS arxiv_cache (query TEXT, k INTEGER, results TEXT, ts TEXT, PRIMARY KEY(query, k))"
        )
        self._conn.commit()

    def get(self, query: str, k: int) -> list[ArxivResult] | None:
        row = self._conn.execute("SELECT results FROM arxiv_cache WHERE query = ? AND k = ?", (query, k)).fetchone()
        if row is None:
            return None
        return [ArxivResult(**r) for r in json.loads(row[0])]

    def put(self, query: str, k: int, results: list[ArxivResult]) -> None:
        payload = json.dumps([r.__dict__ for r in results])
        self._conn.execute(
            "INSERT INTO arxiv_cache(query, k, results, ts) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(query, k) DO UPDATE SET results = excluded.results, ts = excluded.ts",
            (query, k, payload, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def search_arxiv(query: str, k: int = 5, cache: ArxivCache | None = None) -> list[ArxivResult]:
    if cache is not None:
        cached = cache.get(query, k)
        if cached is not None:
            return cached

    client = arxiv.Client(delay_seconds=3)
    search = arxiv.Search(query=query, max_results=k, sort_by=arxiv.SortCriterion.Relevance)
    results = [
        ArxivResult(
            arxiv_id=r.entry_id.rsplit("/", 1)[-1],
            title=r.title,
            summary=r.summary[:500],
            pdf_url=r.pdf_url,
            published=r.published.isoformat() if r.published else "",
        )
        for r in client.results(search)
    ]

    if cache is not None:
        cache.put(query, k, results)
    return results
