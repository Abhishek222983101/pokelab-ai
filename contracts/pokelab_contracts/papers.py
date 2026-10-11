"""PaperPack (§4.2/packs.py) — the claim a reproduction is judged
against."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Claim(BaseModel):
    metric: str
    value: float
    condition: str | None = None
    quote: str
    source_chunk_id: str


class PaperPack(BaseModel):
    paper_id: str
    title: str
    kit: str
    hero: bool = False
    claims: list[Claim] = Field(default_factory=list)
