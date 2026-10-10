import os

import pytest

from pokelab_brain.papers.packs import get_pack
from pokelab_brain.science.comparator_v2 import (
    build_report, config_diff, gather_hypotheses, load_checklist,
)


def test_load_real_grokking_checklist():
    items = load_checklist("grokking")
    assert len(items) == 17
    ids = {i["id"] for i in items}
    assert "seed_variance" in ids
    assert "paper_errata" in ids


def test_config_diff_flags_unspecified_and_differing_fields():
    our_config = {"lr": 1e-3, "wd": 1.0, "p": 113}
    paper_spec = {"lr": 1e-3, "wd": 2.0}  # wd differs, p unspecified by paper
    hyps = config_diff(our_config, paper_spec)
    ids = {h.id for h in hyps}
    assert "differs_wd" in ids
    assert "unspecified_p" in ids
    assert "differs_lr" not in ids  # lr matches, no hypothesis


def test_gather_hypotheses_combines_checklist_and_config_diff():
    hyps = gather_hypotheses("grokking", our_config={"p": 113}, paper_spec={})
    sources = {h.source for h in hyps}
    assert sources == {"checklist", "config_diff"}
    assert len(hyps) == 17 + 1


def _load_env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_build_report_passes_claim_guard(tmp_path):
    from pokelab_brain.llm.providers import GroqProvider
    from pokelab_brain.llm.router import LlmRouter

    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db",
    )
    pack = get_pack("grokking")
    try:
        report = build_report(
            router, route=["groq"], final_result={"test_acc": 0.9654}, metric_key="test_acc",
            pack=pack, our_config={"frac": 0.5}, paper_spec={},
            model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert report.v1.matched
    assert len(report.hypotheses) >= 17
    assert len(report.narrative) > 0
    # the claim guard either passed on attempt 1/2, or we got the honest
    # template fallback — either way, no silently-ungated narrative
    if not report.narrative_is_template_fallback:
        assert "0.9654" in report.narrative or "0.95" in report.narrative or "96" in report.narrative
