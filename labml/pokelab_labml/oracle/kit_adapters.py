"""Which of each kit's real emitted metric keys Oracle should treat as
"primary" (the thing we're forecasting) vs "secondary" (the signal that
catches overfitting/saturation) — P11.5, the generalization that lets
Oracle/Navigator run on ANY kit's real curves, not just grokking's.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KitCurveAdapter:
    primary_key: str
    secondary_key: str
    higher_is_better: bool


KIT_ADAPTERS: dict[str, KitCurveAdapter] = {
    "grokking": KitCurveAdapter("test_acc", "train_acc", higher_is_better=True),
    "materials": KitCurveAdapter("test_r2", "train_r2", higher_is_better=True),
    "distillation": KitCurveAdapter("distilled_student_acc", "teacher_test_acc", higher_is_better=True),
    "nerf": KitCurveAdapter("test_psnr", "train_mse", higher_is_better=True),
}


def get_adapter(kit_name: str) -> KitCurveAdapter:
    if kit_name not in KIT_ADAPTERS:
        raise KeyError(f"no Oracle/Navigator curve adapter for kit {kit_name!r}; known: {sorted(KIT_ADAPTERS)}")
    return KIT_ADAPTERS[kit_name]
