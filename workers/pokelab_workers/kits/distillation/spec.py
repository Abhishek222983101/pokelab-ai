"""The `distillation` kit (P11.1, "Edge") — reproduces the Hinton et al.
2015 knowledge-distillation claim in its clearest form: a big teacher is
trained on a real labeled set; a tiny student trained on only a SMALL
labeled slice of it (hard labels) is compared against the identical
tiny student ALSO given the teacher's soft labels over a much larger
pool it never saw a true label for. The soft-labeled student should
recover far more of the teacher's accuracy than the hard-label-only
student — the "dark knowledge" the teacher carries about class
similarity, transferred onto unlabeled data the small student alone
cannot exploit. Real torch training on a real MNIST subsample (OpenML
id 554, 70000 real handwritten digit images).

[MEASURED on this laptop, seeds 0-5, default config]: teacher reaches
~91-92% test accuracy; the 16-unit student trained on 300 real labeled
examples alone reaches ~80%; the SAME student, given the teacher's soft
labels over an extra 4000 unlabeled real examples, reaches ~89-90% —
6/6 seeds, a robust and reproduced win (an earlier attempt giving BOTH
students the full labeled set showed no reliable benefit — the labeled
set alone already saturates a 16-unit net, leaving no room for soft
labels to help; kept as the honest negative result that led here, see
docs/_parts/08-papers.md).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from pokelab_workers.kits.base import KitContext, register

_MNIST_DATA_ID = 554  # OpenML "mnist_784" — the real 70000-image set


def _load_mnist_subsample(n_total: int, seed: int):
    # sklearn.model_selection pulls in scipy (~0.6s cold) — kept lazy so
    # the warm pool's startup handshake stays fast; see arena/spec.py.
    from sklearn.datasets import fetch_openml

    from pokelab_workers.kits.data_home import ensure_data_home

    bunch = fetch_openml(data_id=_MNIST_DATA_ID, as_frame=False, parser="liac-arff", data_home=ensure_data_home())
    X = bunch.data.astype("float32") / 255.0
    y = bunch.target.astype("int64")
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(X))[:n_total]
    return X[idx], y[idx]


def _make_teacher() -> nn.Module:
    return nn.Sequential(nn.Linear(784, 256), nn.ReLU(), nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, 10))


def _make_student() -> nn.Module:
    return nn.Sequential(nn.Linear(784, 16), nn.ReLU(), nn.Linear(16, 10))


def _accuracy(model: nn.Module, X: torch.Tensor, y: torch.Tensor) -> float:
    with torch.no_grad():
        return float((model(X).argmax(dim=1) == y).float().mean())


def _count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


class DistillationKit:
    name = "distillation"
    version = "1"

    def run(self, ctx: KitContext) -> dict[str, Any]:
        cfg = ctx.config
        seed = int(cfg.get("seed", 0))
        n_total = int(cfg.get("n_total", 10000))
        n_labeled = int(cfg.get("n_labeled", 300))
        n_unlabeled = int(cfg.get("n_unlabeled", 4000))
        teacher_epochs = int(cfg.get("teacher_epochs", 60))
        student_epochs = int(cfg.get("student_epochs", 300))
        temperature = float(cfg.get("temperature", 4.0))
        alpha = float(cfg.get("alpha", 0.4))  # weight on the hard-label term
        teacher_lr = float(cfg.get("teacher_lr", 1e-3))
        student_lr = float(cfg.get("student_lr", 3e-3))

        from sklearn.model_selection import train_test_split

        X, y = _load_mnist_subsample(n_total, seed)
        X_tr, X_test, y_tr, y_test = train_test_split(X, y, test_size=0.2, random_state=seed, stratify=y)
        X_tr_t = torch.tensor(X_tr)
        y_tr_t = torch.tensor(y_tr)
        X_test_t = torch.tensor(X_test)
        y_test_t = torch.tensor(y_test)

        X_labeled, y_labeled = X_tr_t[:n_labeled], y_tr_t[:n_labeled]
        X_unlabeled = X_tr_t[n_labeled : n_labeled + n_unlabeled]

        step = 0

        # Phase 1: the real teacher, trained on the FULL labeled train
        # split (it needs to actually know the task to be worth distilling).
        torch.manual_seed(seed)
        teacher = _make_teacher()
        opt_t = torch.optim.Adam(teacher.parameters(), lr=teacher_lr)
        for _ in range(teacher_epochs):
            if ctx.stop.is_set():
                return {"stopped_in": "teacher", "step": step}
            opt_t.zero_grad()
            loss = F.cross_entropy(teacher(X_tr_t), y_tr_t)
            loss.backward()
            opt_t.step()
            step += 1
            ctx.emit(step, "teacher_test_acc", _accuracy(teacher, X_test_t, y_test_t))
        teacher_acc = _accuracy(teacher, X_test_t, y_test_t)

        with torch.no_grad():
            soft_targets_unlabeled = teacher(X_unlabeled)

        # Phase 2: baseline student — same tiny size, ONLY the small
        # labeled slice, hard labels. Reseeded identically to the
        # distilled student below so the comparison isn't contaminated
        # by whichever one draws a luckier init from leftover RNG state.
        torch.manual_seed(seed + 1)
        baseline = _make_student()
        opt_b = torch.optim.Adam(baseline.parameters(), lr=student_lr)
        for _ in range(student_epochs):
            if ctx.stop.is_set():
                return {"stopped_in": "baseline_student", "step": step, "teacher_acc": teacher_acc}
            opt_b.zero_grad()
            loss = F.cross_entropy(baseline(X_labeled), y_labeled)
            loss.backward()
            opt_b.step()
            step += 1
            ctx.emit(step, "baseline_student_acc", _accuracy(baseline, X_test_t, y_test_t))
        baseline_acc = _accuracy(baseline, X_test_t, y_test_t)

        # Phase 3: distilled student — the SAME small labeled slice,
        # PLUS the teacher's soft labels over the larger unlabeled pool
        # (Hinton 2015 eq. 1/2's KL term, blended with the hard loss).
        torch.manual_seed(seed + 1)  # identical init to the baseline student above
        student = _make_student()
        opt_s = torch.optim.Adam(student.parameters(), lr=student_lr)
        for _ in range(student_epochs):
            if ctx.stop.is_set():
                return {
                    "stopped_in": "distilled_student", "step": step,
                    "teacher_acc": teacher_acc, "baseline_student_acc": baseline_acc,
                }
            opt_s.zero_grad()
            hard_loss = F.cross_entropy(student(X_labeled), y_labeled)
            student_logits_unlabeled = student(X_unlabeled)
            soft_loss = F.kl_div(
                F.log_softmax(student_logits_unlabeled / temperature, dim=1),
                F.softmax(soft_targets_unlabeled / temperature, dim=1),
                reduction="batchmean",
            ) * (temperature ** 2)
            loss = alpha * hard_loss + (1 - alpha) * soft_loss
            loss.backward()
            opt_s.step()
            step += 1
            ctx.emit(step, "distilled_student_acc", _accuracy(student, X_test_t, y_test_t))
        distilled_acc = _accuracy(student, X_test_t, y_test_t)

        return {
            "teacher_acc": teacher_acc,
            "baseline_student_acc": baseline_acc,
            "distilled_student_acc": distilled_acc,
            "teacher_params": _count_params(teacher),
            "student_params": _count_params(student),
            "compression_ratio": _count_params(teacher) / _count_params(student),
            "recovery_fraction": distilled_acc / teacher_acc if teacher_acc > 0 else 0.0,
            "kd_beat_baseline": distilled_acc > baseline_acc,
        }


kit = register(DistillationKit())
