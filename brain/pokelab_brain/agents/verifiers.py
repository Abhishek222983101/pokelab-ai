"""Verifiers (§6.3.5): every PlanStep.accept check is executed by CODE,
never the LLM. A check string is "name:args" (e.g.
"metric_threshold:test_acc,>=,0.95"); `run_check` dispatches to the
matching function and returns a plain bool + reason, which becomes part
of the reward's quality term.
"""
from __future__ import annotations

import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}


@dataclass
class CheckResult:
    passed: bool
    reason: str


def file_exists(args: str, context: dict[str, Any]) -> CheckResult:
    artifact_name = args
    path = context.get("artifacts", {}).get(artifact_name)
    if path is None:
        return CheckResult(False, f"no artifact registered for {artifact_name!r}")
    exists = Path(path).exists()
    return CheckResult(exists, f"{path} exists={exists}")


def json_schema_valid(args: str, context: dict[str, Any]) -> CheckResult:
    artifact_name = args
    value = context.get("artifacts", {}).get(artifact_name)
    # "valid" here means: present and is a dict/list (a real schema check
    # would validate against a pydantic model; this is deliberately the
    # same honest minimal version jsonio.extract_json already relies on)
    ok = isinstance(value, (dict, list))
    return CheckResult(ok, f"artifact {artifact_name!r} is {type(value).__name__}")


def config_validates(args: str, context: dict[str, Any]) -> CheckResult:
    # templates say "config_validates:kit" = whichever kit this project resolved to
    kit_name = context.get("kit", args) if args == "kit" else args
    known_kits = context.get("known_kits", {"smoke", "grokking", "distillation", "nerf", "materials", "arena"})
    ok = kit_name in known_kits
    return CheckResult(ok, f"kit {kit_name!r} known={ok}")


def job_completed(args: str, context: dict[str, Any]) -> CheckResult:
    job_key = args
    job = context.get("jobs", {}).get(job_key)
    if job is None:
        return CheckResult(False, f"no job registered for {job_key!r}")
    ok = job.get("status") == "ok"
    return CheckResult(ok, f"job {job_key!r} status={job.get('status')}")


def metric_present(args: str, context: dict[str, Any]) -> CheckResult:
    key = args
    final = context.get("final", {})
    ok = key in final and final[key] is not None
    return CheckResult(ok, f"metric {key!r} present={ok}")


def metric_threshold(args: str, context: dict[str, Any]) -> CheckResult:
    key, op_str, value_str = [a.strip() for a in args.split(",")]
    final = context.get("final", {})
    if key not in final or final[key] is None:
        return CheckResult(False, f"metric {key!r} missing")
    op = _OPS.get(op_str)
    if op is None:
        return CheckResult(False, f"unknown operator {op_str!r}")
    achieved = final[key]
    threshold = float(value_str)
    ok = op(achieved, threshold)
    return CheckResult(ok, f"{key}={achieved} {op_str} {threshold} -> {ok}")


def report_has_sections(args: str, context: dict[str, Any]) -> CheckResult:
    required_sections = [s.strip() for s in args.split(",")]
    report_text = context.get("report_text", "")
    missing = [s for s in required_sections if s.lower() not in report_text.lower()]
    return CheckResult(not missing, f"missing sections: {missing}" if missing else "all sections present")


def numbers_match_evidence(args: str, context: dict[str, Any]) -> CheckResult:
    """The claim-guard, reused as a verifier — comparator_v2 already
    implements this; here we just check the flag it sets."""
    ok = not context.get("narrative_is_template_fallback", False) and context.get("claim_guard_passed", True)
    return CheckResult(ok, f"claim guard passed={ok}")


_CHECKS = {
    "file_exists": file_exists,
    "json_schema_valid": json_schema_valid,
    "config_validates": config_validates,
    "job_completed": job_completed,
    "metric_present": metric_present,
    "metric_threshold": metric_threshold,
    "report_has_sections": report_has_sections,
    "numbers_match_evidence": numbers_match_evidence,
}


def run_check(check_str: str, context: dict[str, Any]) -> CheckResult:
    if ":" in check_str:
        name, args = check_str.split(":", 1)
    else:
        name, args = check_str, ""
    fn = _CHECKS.get(name)
    if fn is None:
        return CheckResult(False, f"unknown check {name!r}")
    return fn(args, context)


def run_all_checks(check_strs: list[str], context: dict[str, Any]) -> tuple[bool, list[CheckResult]]:
    results = [run_check(c, context) for c in check_strs]
    return all(r.passed for r in results), results
