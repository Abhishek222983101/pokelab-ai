"""Comparator v2 (§6.10): v1 (comparator.py) just says matched/not. This
adds *why*: candidate hypotheses from the paper's checklist + our config
diff, diagnostic jobs to actually test the cheap ones, and a narrative
that's only allowed to state numbers that are in the evidence table (the
claim-guard) — so the explanation can't hallucinate a number no run
actually produced.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.papers.packs import PaperPack
from pokelab_brain.science.comparator import ComparisonReport, compare


@dataclass
class Hypothesis:
    source: str  # "checklist" | "config_diff"
    id: str
    description: str
    cheap_to_test: bool = False
    evidence_score: float | None = None  # filled in by a diagnostic run, if any


def load_checklist(paper_id: str, checklists_dir: str | Path | None = None) -> list[dict]:
    base = Path(checklists_dir) if checklists_dir else Path(__file__).parent / "checklists"
    path = base / f"{paper_id}.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("items", [])


def config_diff(our_config: dict, paper_spec: dict) -> list[Hypothesis]:
    """Every field we had to assume (not in paper_spec, or different from
    it) becomes a hypothesis — §6.10.2b."""
    hyps = []
    for key, our_value in our_config.items():
        if key not in paper_spec:
            hyps.append(Hypothesis(
                source="config_diff", id=f"unspecified_{key}",
                description=f"'{key}={our_value}' was not specified by the paper — we assumed it",
            ))
        elif paper_spec[key] != our_value:
            hyps.append(Hypothesis(
                source="config_diff", id=f"differs_{key}",
                description=f"'{key}' differs: ours={our_value!r} vs paper={paper_spec[key]!r}",
            ))
    return hyps


def gather_hypotheses(paper_id: str, our_config: dict, paper_spec: dict) -> list[Hypothesis]:
    checklist_hyps = [
        Hypothesis(source="checklist", id=item["id"], description=item["description"])
        for item in load_checklist(paper_id)
    ]
    return checklist_hyps + config_diff(our_config, paper_spec)


_NARRATIVE_PROMPT = """Write a short, factual explanation of a reproduction result, using ONLY
the numbers given in this evidence table. Do not invent or round differently than shown.

Evidence table:
{evidence}

Reply with 2-4 plain sentences, no JSON, no markdown.
"""

_NUMBER_RE = re.compile(r"-?\d+\.?\d*")


def _claim_guard(narrative: str, evidence_numbers: set[str]) -> bool:
    """Every number in the narrative must appear (allowing rounding to 2
    decimal places) in the evidence table — §6.10.4."""
    for match in _NUMBER_RE.findall(narrative):
        try:
            value = float(match)
        except ValueError:
            continue
        rounded_candidates = {f"{value:.0f}", f"{value:.1f}", f"{value:.2f}", f"{value:.4f}", match}
        if not (rounded_candidates & evidence_numbers):
            return False
    return True


@dataclass
class ComparisonReportV2:
    v1: ComparisonReport
    hypotheses: list[Hypothesis]
    narrative: str
    narrative_is_template_fallback: bool = False


def _template_narrative(v1: ComparisonReport) -> str:
    return v1.narrative  # comparator v1's narrative is already evidence-only


def build_report(
    router: LlmRouter,
    route: list[str],
    final_result: dict | None,
    metric_key: str,
    pack: PaperPack,
    our_config: dict,
    paper_spec: dict,
    **llm_kwargs,
) -> ComparisonReportV2:
    v1 = compare(final_result, metric_key, pack)
    hypotheses = gather_hypotheses(pack.paper_id, our_config, paper_spec)

    evidence_numbers = set()
    for value in (v1.achieved_value, v1.target_value, v1.gap):
        if value is not None:
            evidence_numbers |= {f"{value:.0f}", f"{value:.1f}", f"{value:.2f}", f"{value:.4f}"}

    evidence_text = (
        f"achieved={v1.achieved_value}, target={v1.target_value}, gap={v1.gap:.4f}, matched={v1.matched}"
    )
    result = router.complete(
        messages=[{"role": "user", "content": _NARRATIVE_PROMPT.format(evidence=evidence_text)}],
        route=route, max_tokens=300, **llm_kwargs,
    )
    narrative = result.content.strip()

    if not _claim_guard(narrative, evidence_numbers):
        # §6.10.4: regenerate once, else template text
        result2 = router.complete(
            messages=[{"role": "user", "content": _NARRATIVE_PROMPT.format(evidence=evidence_text)}],
            route=route, max_tokens=300, **llm_kwargs,
        )
        if _claim_guard(result2.content.strip(), evidence_numbers):
            narrative = result2.content.strip()
        else:
            return ComparisonReportV2(v1=v1, hypotheses=hypotheses, narrative=_template_narrative(v1), narrative_is_template_fallback=True)

    return ComparisonReportV2(v1=v1, hypotheses=hypotheses, narrative=narrative)
