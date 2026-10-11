"""The event envelope (§10.4's `events` table) — the single shape every
event in the system has, in every language. Rust's lab_store::Event,
Python's brain code, and the TS LabEvent interface are all meant to be
the SAME shape as this; this file is the one to change first if that
shape ever needs to change.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Display(BaseModel):
    importance: int = 0  # 0-3
    bubble: str | None = None
    sfx: str | None = None
    spotlight: bool | None = None


class Event(BaseModel):
    seq: int
    ts: str
    kind: str
    v: int = 1
    project: str | None = None
    actor: str
    corr: str | None = None
    causation: int | None = None
    payload: dict[str, Any]
    display: Display | None = None


class NewEvent(BaseModel):
    """What a publisher sends — everything but `seq`/`ts`, which labd
    assigns on commit."""
    kind: str
    v: int = 1
    project: str | None = None
    actor: str
    corr: str | None = None
    causation: int | None = None
    payload: dict[str, Any]
    display: Display | None = None
