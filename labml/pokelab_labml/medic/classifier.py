"""The Bug Gym classifier wraps signatures.classify with a fallback: a
signature nothing recognizes becomes `class="unknown"`, which is itself
useful (it's the signal that the fixes table needs a new rule, not that
the job secretly succeeded).
"""
from __future__ import annotations

from pokelab_labml.medic.signatures import Diagnosis, classify


def diagnose(error_sig: str | None) -> Diagnosis:
    if not error_sig:
        return Diagnosis(error_class="none", suggested_fix="", matched_rule="")
    diagnosis = classify(error_sig)
    if diagnosis is not None:
        return diagnosis
    return Diagnosis(error_class="unknown", suggested_fix="needs a human look + a new Medic rule", matched_rule="")
