"""The real `distillation` kit (P11.1) on a real MNIST subsample. Runs
the DEFAULT config (not a shrunk CI variant) because the whole point of
this kit is a specific, fragile claim — "soft labels beat hard labels
at this exact small-student/small-label-budget scale" — that only shows
up reliably at this size (see spec.py's docstring for the earlier,
honestly-reported negative result at a different scale).
"""
from pokelab_workers.kits.base import KitContext, SimpleStopToken
from pokelab_workers.kits.distillation.spec import kit as distillation_kit


def test_distillation_beats_hard_label_only_baseline():
    ctx = KitContext(job_id="t1", config={"seed": 0}, emit=lambda s, k, v: None, stop=SimpleStopToken())
    final = distillation_kit.run(ctx)

    assert final["teacher_acc"] > 0.85
    assert final["kd_beat_baseline"] is True
    assert final["distilled_student_acc"] > final["baseline_student_acc"]
    assert final["student_params"] < final["teacher_params"]
    assert 0.0 < final["recovery_fraction"] <= 1.05


def test_distillation_kit_honours_stop_in_teacher_phase():
    ctx = KitContext(job_id="t2", config={}, emit=lambda s, k, v: None, stop=_AlwaysStop())
    final = distillation_kit.run(ctx)
    assert final["stopped_in"] == "teacher"
    assert final["step"] == 0


class _AlwaysStop:
    def is_set(self) -> bool:
        return True
