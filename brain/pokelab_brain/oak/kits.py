"""What Oak needs to know about each paper's kit to run and JUDGE it (brain-side single source; the
web's lab/gyms.ts mirrors metric/claim/floor for the Gym HP): which `final` key is the result, the
curated claim it is judged against, the metric's real floor, a seconds-scale smoke config (proves
the kit + environment work) and the demo-scale full config.

Configs are the ones measured on this laptop (CPU-safe; the grokking full run uses the MLP variant
that groks on CPU in seconds — the transformer/GPU config is the documented hero run).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KitProfile:
    paper: str
    kit: str
    final_key: str      # key in the kit's `final` dict that is the reproduced number
    live_key: str       # metric streamed per step (the Gym's HP)
    claim: float
    floor: float
    smoke: dict[str, Any] = field(default_factory=dict)
    full: dict[str, Any] = field(default_factory=dict)
    pdf: str | None = None  # data/papers/<pdf>, when the paper is on disk


KITS: dict[str, KitProfile] = {
    "grokking": KitProfile(
        paper="grokking", kit="grokking", final_key="test_acc", live_key="test_acc", claim=0.95, floor=1 / 113,
        smoke={"model": "mlp", "p": 23, "frac": 0.5, "steps": 200, "eval_every": 50, "d_hidden": 32, "d_emb": 16, "device": "cpu"},
        full={"model": "mlp", "p": 53, "frac": 0.5, "steps": 6000, "eval_every": 100, "d_hidden": 128, "d_emb": 64, "lr": 3e-3, "stop_at": 0.99},
        pdf="2201.02177.pdf",
    ),
    "materials": KitProfile(
        paper="materials", kit="materials", final_key="test_r2", live_key="test_r2", claim=0.9, floor=0.0,
        smoke={"n_estimators": 10, "trees_per_step": 10},
        full={"n_estimators": 300, "trees_per_step": 20},
    ),
    "distillation": KitProfile(
        paper="distillation", kit="distillation", final_key="distilled_student_acc", live_key="distilled_student_acc",
        claim=0.88, floor=0.1,
        smoke={"n_total": 1500, "teacher_epochs": 5, "student_epochs": 10, "n_labeled": 100, "n_unlabeled": 500},
        full={},
    ),
    "nerf": KitProfile(
        paper="nerf", kit="nerf", final_key="final_test_psnr", live_key="test_psnr", claim=15.0, floor=9.6,
        smoke={"downsample_factor": 10, "n_samples": 16, "iters": 20, "test_every": 10},
        full={"downsample_factor": 4, "n_samples": 32, "iters": 200, "test_every": 20},
    ),
    "arena": KitProfile(
        paper="arena", kit="arena", final_key="tree_mean", live_key="tree_fold_acc", claim=0.84, floor=0.5,
        smoke={"dataset": "magictelescope", "n_subsample": 600, "n_folds": 3},
        full={"dataset": "magictelescope", "variant": "+noise", "n_subsample": 2000, "n_folds": 5},
    ),
}

# words a researcher might use → the paper pack id
PAPER_ALIASES = {
    "grokking": "grokking", "grok": "grokking",
    "distillation": "distillation", "distill": "distillation", "knowledge distillation": "distillation", "hinton": "distillation",
    "nerf": "nerf", "radiance": "nerf", "3d": "nerf",
    "materials": "materials", "matbench": "materials", "superconductor": "materials",
    "arena": "arena", "tabular": "arena", "tree-based": "arena", "grinsztajn": "arena",
}


def paper_for(text: str) -> str | None:
    lowered = text.lower()
    for word, paper in PAPER_ALIASES.items():
        if word in lowered:
            return paper
    return None


def verdict(profile: KitProfile, value: float | None) -> str:
    """REPRODUCED at/over the claim; PARTIAL when it closed most of the gap from the real floor; FAILED
    otherwise. Same thresholds the comparator uses for the headline claim (§6.10)."""
    if value is None:
        return "FAILED"
    if value >= profile.claim:
        return "REPRODUCED"
    closed = (value - profile.floor) / max(profile.claim - profile.floor, 1e-9)
    return "PARTIAL" if closed >= 0.75 else "FAILED"
