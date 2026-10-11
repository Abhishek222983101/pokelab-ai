"""P12.4 — the acceptance suite's source of truth: every AC from
docs/_parts/12-demo.md §12.3, mapped to the REAL test(s) that prove it
(or an honest reason it's not proven yet). This is deliberately a data
structure, not test functions, so scripts/run_acceptance_suite.py can
both RUN the real evidence tests and generate a report, and a thin
pytest test can check this mapping doesn't silently rot (a referenced
test file/function that no longer exists is a real bug in this
mapping, same discipline as the game's binding audit).

Status meanings:
  "real"            — the AC's actual pass condition is covered by a
                       real, currently-passing automated test.
  "partial"         — part of the AC is real and tested; the rest is
                       either untested at this scale/scope or depends
                       on infrastructure not available in this
                       environment (see `note`).
  "not_implemented" — the feature this AC names does not exist in the
                       codebase yet. Said plainly, not glossed over.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    requirement: str
    status: str  # "real" | "partial" | "not_implemented"
    evidence: list[str] = field(default_factory=list)  # "path/to/test.py::test_name" or "path/to/test.py" (whole file)
    note: str = ""


ACCEPTANCE_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        "AC-1", "Grokking key result reproduced autonomously", "real",
        ["brain/tests/test_verifiers.py", "workers/tests/test_grokking_kit_tiny.py",
         "brain/tests/test_papers_claims_and_packs.py::test_grokking_pack_curated_claim"],
    ),
    AcceptanceCriterion(
        "AC-2", "What-if wd=0 investigated", "partial",
        ["brain/tests/test_oak_planner.py::test_all_templates_load_and_validate_clean"],
        note="the whatif plan template is real, validated, and loadable (parametrized "
        "test covers it); the specific 'Oracle early-stops wd=0 and records "
        "gpu_s_saved' metric is not implemented — no gpu_s_saved field exists "
        "anywhere in the codebase.",
    ),
    AcceptanceCriterion(
        "AC-3", "Differences explained with evidence", "real",
        ["brain/tests/test_comparator_v2.py"],
    ),
    AcceptanceCriterion(
        "AC-4", "Multi-domain (>=3 papers from >=3 PS domains)", "real",
        ["brain/tests/test_papers_claims_and_packs.py"],
        note="5 real curated PaperPacks now: grokking (ML theory), materials (materials "
        "science), distillation (ML/edge), nerf (3D/vision), arena (tabular) — well past "
        "the >=3-domains bar, each with a real reproduced/partial result (P11).",
    ),
    AcceptanceCriterion(
        "AC-5", "Capability analysis", "real",
        ["brain/tests/test_oak_capabilities.py"],
    ),
    AcceptanceCriterion(
        "AC-6", "Selection is learned", "partial",
        ["brain/tests/test_oak_scheduler.py"],
        note="ThompsonSelector is real and wired into the real scheduler (proven against "
        "a real labd+warm pool); the specific claim 'cumulative reward > round-robin in a "
        "replay simulation' has no dedicated test comparing the two policies.",
    ),
    AcceptanceCriterion(
        "AC-7", "Spawn", "real",
        ["brain/tests/test_spawn.py", "brain/tests/test_lifecycle_loop_live.py"],
        note="lifecycle_loop_live.py is the strong version — a REAL capability gap "
        "triggers a REAL spawn with no test code calling spawn directly.",
    ),
    AcceptanceCriterion("AC-8", "Refine", "real", ["brain/tests/test_refine.py"]),
    AcceptanceCriterion("AC-9", "Merge", "real", ["brain/tests/test_merge.py"]),
    AcceptanceCriterion(
        "AC-10", "Retire", "real",
        ["brain/tests/test_retire.py", "brain/tests/test_lifecycle_loop_live.py"],
    ),
    AcceptanceCriterion(
        "AC-11", "Reward loop", "real",
        ["brain/tests/test_reward_v2.py::test_human_feedback_pulls_reward_toward_it"],
    ),
    AcceptanceCriterion(
        "AC-12", "Memory dedup (<300ms)", "not_implemented",
        [],
        note="no job.deduped/memory.hit event kind exists anywhere in the codebase. "
        "pokedex.py is a fix-library (lessons/fixes with evidence), a related but "
        "different feature — not a config-resubmission dedup cache.",
    ),
    AcceptanceCriterion(
        "AC-13", "Failure repair (Medic 0 LLM calls, Debugger novel-bug)", "not_implemented",
        [],
        note="no dedicated zero-LLM-call Medic triage system exists. refine.py has a "
        "docstring reference to 'medic' but no implementation of the AC's specific "
        "pass condition (<1s triage, zero LLM calls, retrieved similar cases).",
    ),
    AcceptanceCriterion(
        "AC-14", "Oracle (AUROC >= 0.85 at 20% prefix)", "not_implemented",
        ["labml/tests/test_oracle.py"],
        note="the Oracle pipeline (features -> GBM/logistic classifier) is real and "
        "tested end to end, but no AUROC is computed anywhere, and the real curve "
        "count (4-5, see P5.1/P5.2) is explicitly documented as too small to make "
        "this claim honestly — see docs/PROGRESS.md.",
    ),
    AcceptanceCriterion(
        "AC-15", "Navigator (boundary F1 >= 0.9, fewer runs than grid)", "not_implemented",
        ["labml/tests/test_navigator.py", "labml/tests/test_oracle_navigator_per_kit.py"],
        note="Navigator's GP + UCB acquisition is real and proven on two real kits "
        "(grokking, materials), but only ever on a single 1D knob — no 2D wd x frac "
        "boundary-mapping or F1 metric exists.",
    ),
    AcceptanceCriterion(
        "AC-16", "Remote compute (Kaggle + Colab, same panel)", "partial",
        ["workers/tests/test_kaggle_runner.py", "workers/tests/test_colab_runner.py"],
        note="both runners are real-tested against a real captured Kaggle log fixture "
        "(a genuine format bug was found and fixed there this way) — but this "
        "environment has no live Kaggle/Colab credentials, so no job has actually "
        "completed on either remote service, and the 'same Experiments panel' UI "
        "claim is unverified against a live remote run.",
    ),
    AcceptanceCriterion(
        "AC-17", "Environment handling (Env Engineer auto-repair)", "not_implemented",
        [],
        note="no Env Engineer / uv-install-from-allowlist auto-repair exists anywhere "
        "in the codebase.",
    ),
    AcceptanceCriterion(
        "AC-18", "Mobile control (<1s)", "partial",
        ["core/crates/lab-gateway/tests/auth.rs", "core/crates/lab-gateway/tests/kill_job_e2e.rs"],
        note="pairing (QR->claim) and kill-from-client are real and E2E-tested near-"
        "instantly; approve/reject of a spawn proposal and redirect specifically FROM "
        "the phone pairing flow are not covered by a dedicated test.",
    ),
    AcceptanceCriterion(
        "AC-19", "Redirect (project.plan_revised)", "not_implemented",
        [],
        note="no plan_revised event or redirect-without-restart mechanism exists; "
        "voice.py (real Whisper transcription, tested) is the input half of what a "
        "redirect feature would need, but nothing consumes a transcript into a plan "
        "diff today.",
    ),
    AcceptanceCriterion(
        "AC-20", "Notes & documents", "real",
        ["brain/tests/test_author_email.py", "brain/tests/test_notes.py"],
    ),
    AcceptanceCriterion(
        "AC-21", "Interface binding & scale (>=6 agents, >=3 runs, 2 projects @ >=50fps)", "partial",
        ["web/game/__tests__/bindingAudit.test.ts"],
        note="the event-id binding discipline (every on-screen thing traces to a real "
        "event, structurally enforced) is real and tested; the specific scale target "
        "(6 agents/3 runs/2 projects at once, >=50fps) has not been load-tested — "
        "web/scripts/perf_probe.mjs (P12.3) measured 60fps but under light load "
        "(2-3 real jobs), not this AC's named scale.",
    ),
    AcceptanceCriterion(
        "AC-22", "Fluidity (p95 event->screen < 150ms)", "real",
        ["web/lib/__tests__/perf.test.ts"],
        note="P12.3's real measured result against a live labd: p50 0-1ms, p95 1-5ms, "
        "p99 3-7ms — see var/reports/perf.json from the last probe run.",
    ),
    AcceptanceCriterion(
        "AC-23", "Resilience", "real",
        ["core/crates/lab-jobs/tests/chaos_kill_worker.rs",
         "core/crates/lab-gateway/tests/chaos_kill_brain_e2e.rs",
         "brain/tests/test_router.py::test_fallback_skips_a_failing_provider"],
        note="P12.2's chaos drills: kill-worker (a real bug found + fixed), kill-brain "
        "(job survives), network/429 fault injection via the router. disk-low has a "
        "real guard + a real primitive test, not a full fill-the-disk drill (unsafe "
        "to automate) — see scripts/chaos/README.md.",
    ),
    AcceptanceCriterion(
        "AC-24", "Non-paper inputs (question, CSV, repo path)", "real",
        ["brain/tests/test_oak_intake.py::test_template_matched_request_skips_llm",
         "brain/tests/test_data_and_repo_tools.py"],
    ),
    AcceptanceCriterion(
        "AC-25", "Discovery (Scout finds related papers via arXiv)", "real",
        ["brain/tests/test_discover.py::test_real_arxiv_search_finds_the_grokking_paper"],
    ),
]


def summarize() -> dict[str, int]:
    counts = {"real": 0, "partial": 0, "not_implemented": 0}
    for ac in ACCEPTANCE_CRITERIA:
        counts[ac.status] += 1
    return counts
