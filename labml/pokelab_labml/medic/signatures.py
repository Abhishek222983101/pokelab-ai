"""Medic (§7.4, Bug Gym): turns a raw error signature/traceback tail into
a normalized class with a known fix, when there IS a known fix — an LLM
call to classify a one-line CUDA OOM error is slower and less reliable
than a regex a human already wrote once.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (pattern, class, suggested fix) — order matters, first match wins.
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"CUDA out of memory|OutOfMemoryError", re.I), "oom", "halve batch/model width, retry once"),
    (re.compile(r"unknown_kit", re.I), "unknown_kit", "check the kit name against the registry"),
    (re.compile(r"\bnan\b|Inf|inf\b", re.I), "nan", "lower the learning rate or add gradient clipping"),
    (re.compile(r"CUDA error|cuda runtime error|device-side assert", re.I), "cuda_error", "restart the worker slot"),
    (re.compile(r"Connection refused|ConnectionError|timed? ?out", re.I), "network", "check labd/network reachability"),
    (re.compile(r"FileNotFoundError|No such file or directory", re.I), "missing_file", "run `just fetch`"),
]


@dataclass
class Diagnosis:
    error_class: str
    suggested_fix: str
    matched_rule: str


def classify(error_sig: str) -> Diagnosis | None:
    for pattern, cls, fix in _RULES:
        if pattern.search(error_sig):
            return Diagnosis(error_class=cls, suggested_fix=fix, matched_rule=pattern.pattern)
    return None
