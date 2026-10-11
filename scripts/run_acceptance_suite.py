#!/usr/bin/env python3
"""P12.4 — runs the REAL evidence test(s) for every AC that has any
(status "real" or "partial") and writes a real pass/fail report to
var/reports/acceptance.json. "not_implemented" ACs aren't run (there's
nothing to run) — they're reported with their honest reason straight
from acceptance.py.

Each AC's evidence tests run through THEIR OWN project's real venv
(brain/.venv, or a Rust/cargo invocation, or a web/vitest invocation) —
this script doesn't fake a shared Python environment across Rust/TS/
Python; it shells out to each.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "brain"))

from pokelab_brain.acceptance import ACCEPTANCE_CRITERIA  # noqa: E402


def _group_by_runner(paths: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"brain_pytest": [], "workers_pytest": [], "labml_pytest": [], "cargo": [], "vitest": []}
    for p in paths:
        file_path = p.split("::", 1)[0]
        if file_path.startswith("brain/"):
            groups["brain_pytest"].append(p)
        elif file_path.startswith("workers/"):
            groups["workers_pytest"].append(p)
        elif file_path.startswith("labml/"):
            groups["labml_pytest"].append(p)
        elif file_path.startswith("core/"):
            groups["cargo"].append(file_path)
        elif file_path.startswith("web/"):
            groups["vitest"].append(file_path)
    return groups


def _run_pytest(project_dir: str, refs: list[str]) -> bool:
    if not refs:
        return True
    rel_refs = [os.path.relpath(os.path.join(ROOT, r.split("::", 1)[0]), os.path.join(ROOT, project_dir))
                + (f"::{r.split('::', 1)[1]}" if "::" in r else "")
                for r in refs]
    venv_python = os.path.join(ROOT, project_dir, ".venv", "bin", "python")
    cmd = [venv_python, "-m", "pytest", *rel_refs, "-q"]
    result = subprocess.run(cmd, cwd=os.path.join(ROOT, project_dir), capture_output=True, text=True)
    return result.returncode == 0


def _run_cargo_test(test_files: list[str]) -> bool:
    if not test_files:
        return True
    ok = True
    for f in set(test_files):
        name = os.path.splitext(os.path.basename(f))[0]
        is_unit = "/tests/" not in f
        if is_unit:
            # a src-level #[cfg(test)] module — run the whole package's unit tests
            pkg = f.split("/crates/")[1].split("/")[0]
            cmd = ["cargo", "test", "--package", pkg, "--lib"]
        else:
            pkg = f.split("/crates/")[1].split("/")[0]
            cmd = ["cargo", "test", "--package", pkg, "--test", name]
        result = subprocess.run(cmd, cwd=os.path.join(ROOT, "core"), capture_output=True, text=True)
        ok = ok and result.returncode == 0
    return ok


def _run_vitest(test_files: list[str]) -> bool:
    if not test_files:
        return True
    rel = [os.path.relpath(os.path.join(ROOT, f), os.path.join(ROOT, "web")) for f in set(test_files)]
    cmd = ["npx", "vitest", "run", *rel]
    result = subprocess.run(cmd, cwd=os.path.join(ROOT, "web"), capture_output=True, text=True)
    return result.returncode == 0


def run_evidence_for(ac) -> bool | None:
    # "not_implemented" ACs may still cite adjacent real tests for honest
    # context (e.g. Oracle's pipeline works even though its AUROC target
    # isn't measured) — those are NOT run as "proof of this AC", only
    # real/partial ACs' evidence is actually proof.
    if ac.status == "not_implemented" or not ac.evidence:
        return None
    groups = _group_by_runner(ac.evidence)
    results = [
        _run_pytest("brain", groups["brain_pytest"]),
        _run_pytest("workers", groups["workers_pytest"]),
        _run_pytest("labml", groups["labml_pytest"]),
        _run_cargo_test(groups["cargo"]),
        _run_vitest(groups["vitest"]),
    ]
    return all(results)


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": [],
    }
    for ac in ACCEPTANCE_CRITERIA:
        evidence_passed = run_evidence_for(ac)
        entry = {
            "id": ac.id,
            "requirement": ac.requirement,
            "status": ac.status,
            "evidence": ac.evidence,
            "evidence_passed": evidence_passed,
            "note": ac.note,
        }
        report["criteria"].append(entry)
        mark = "PASS" if evidence_passed else ("N/A" if evidence_passed is None else "FAIL")
        print(f"[{ac.status:16s}] {ac.id}: {ac.requirement}  ({mark})")

    report["summary"] = {
        "real": sum(1 for c in report["criteria"] if c["status"] == "real"),
        "partial": sum(1 for c in report["criteria"] if c["status"] == "partial"),
        "not_implemented": sum(1 for c in report["criteria"] if c["status"] == "not_implemented"),
        "evidence_tests_failed": sum(1 for c in report["criteria"] if c["evidence_passed"] is False),
    }

    out_dir = os.path.join(ROOT, "var", "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "acceptance.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {out_path}")
    print(json.dumps(report["summary"], indent=2))

    return 1 if report["summary"]["evidence_tests_failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
