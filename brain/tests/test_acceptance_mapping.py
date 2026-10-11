"""P12.4 — proves the acceptance mapping itself doesn't rot: every
evidence path it cites really exists on disk, and every `::test_name`
it cites really is a test function in that file. Not a claim that the
AC passes (scripts/run_acceptance_suite.py actually runs the tests for
that) — just that the citation isn't a dangling reference nobody would
ever notice went stale.
"""
import os
import re

from pokelab_brain.acceptance import ACCEPTANCE_CRITERIA

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _split_evidence(ref: str) -> tuple[str, str | None]:
    if "::" in ref:
        path, name = ref.split("::", 1)
        return path, name
    return ref, None


def test_every_evidence_path_exists():
    missing = []
    for ac in ACCEPTANCE_CRITERIA:
        for ref in ac.evidence:
            path, _ = _split_evidence(ref)
            if not os.path.exists(os.path.join(ROOT, path)):
                missing.append(f"{ac.id}: {path}")
    assert not missing, f"dangling evidence paths: {missing}"


def test_every_cited_test_function_exists_in_its_file():
    missing = []
    for ac in ACCEPTANCE_CRITERIA:
        for ref in ac.evidence:
            path, name = _split_evidence(ref)
            if name is None or not path.endswith(".py"):
                continue
            full = os.path.join(ROOT, path)
            with open(full) as f:
                source = f.read()
            if not re.search(rf"def {re.escape(name)}\(", source):
                missing.append(f"{ac.id}: {ref}")
    assert not missing, f"cited test functions not found: {missing}"


def test_every_ac_has_a_status_and_a_reason_if_not_real():
    for ac in ACCEPTANCE_CRITERIA:
        assert ac.status in {"real", "partial", "not_implemented"}
        if ac.status != "real":
            assert ac.note, f"{ac.id} is {ac.status} but has no explanation why"


def test_all_25_acceptance_criteria_are_mapped():
    ids = {ac.id for ac in ACCEPTANCE_CRITERIA}
    expected = {f"AC-{i}" for i in range(1, 26)}
    assert ids == expected
