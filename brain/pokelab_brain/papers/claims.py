"""Pulls quantitative claims ("test accuracy reaches 99% by step 10^4")
out of a paper chunk, via the LLM router. This is the ONE place an LLM's
output about a paper's numbers is trusted provisionally — the comparator
(P4.9/P7.1) always checks our own measured result against these, and a
curated PaperPack (packs.py) can override an extracted claim with a
hand-verified one for the hero demo, where a hallucinated claim would be
embarrassing on stage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pokelab_brain.llm.jsonio import extract_json
from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.papers.ingest import PaperChunk

_EXTRACT_PROMPT = """You extract quantitative claims from a machine learning paper excerpt.
A claim is a specific number tied to a named metric (accuracy, loss, PSNR, MAE, etc.),
optionally with a condition (a step count, a dataset, a model size).

Reply with ONLY a JSON array (no prose, no code fence) of objects shaped like:
{{"metric": "test accuracy", "value": 0.99, "condition": "by 10^4 optimization steps", "quote": "<the exact sentence this came from>"}}

If the excerpt has no such claims, reply with exactly: []

Excerpt:
---
{text}
---
"""


@dataclass
class Claim:
    metric: str
    value: float
    condition: str | None
    quote: str
    source_chunk_id: str


def extract_claims(router: LlmRouter, chunk: PaperChunk, route: list[str], **llm_kwargs: Any) -> list[Claim]:
    prompt = _EXTRACT_PROMPT.format(text=chunk.text[:3000])
    result = router.complete(
        messages=[{"role": "user", "content": prompt}],
        route=route,
        max_tokens=800,
        **llm_kwargs,
    )
    parsed = extract_json(result.content)
    if not isinstance(parsed, list):
        return []

    claims = []
    for item in parsed:
        if not isinstance(item, dict) or "metric" not in item or "value" not in item:
            continue
        try:
            value = float(item["value"])
        except (TypeError, ValueError):
            continue
        claims.append(
            Claim(
                metric=str(item["metric"]),
                value=value,
                condition=item.get("condition"),
                quote=str(item.get("quote", ""))[:500],
                source_chunk_id=chunk.chunk_id,
            )
        )
    return claims
