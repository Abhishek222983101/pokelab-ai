"""The real `nerf` kit (P11.2) on the real tiny_nerf lego dataset.

[BUG FOUND & FIXED during this phase]: the first version of the model
used plain ReLU for density, which either saturated opacity to ~1 at
init (zero gradient to reduce it back down) or died at exactly 0 (zero
ReLU gradient to ever raise it) depending on init luck — the held-out
test view's rendered loss then matched EXACTLY the all-background-pixel
baseline (mean(target^2)) no matter how long training ran, since the
model's output never actually depended on its weights at that view.
Fixed with softplus density + a scaled-down final-layer init
(model.py). This test's core assertion is exactly the regression check
for that bug: real PSNR improvement over training, strictly above the
all-zero-prediction baseline computed straight from the dataset.
"""
import numpy as np

from pokelab_workers.kits.base import KitContext, SimpleStopToken
from pokelab_workers.kits.nerf.data import load_tiny_nerf_data
from pokelab_workers.kits.nerf.spec import _downsample, _psnr
from pokelab_workers.kits.nerf.spec import kit as nerf_kit


def test_nerf_kit_improves_psnr_past_the_all_zero_baseline():
    emits = []
    cfg = {"downsample_factor": 4, "n_samples": 32, "iters": 120, "test_every": 40, "seed": 0}
    ctx = KitContext(job_id="t1", config=cfg, emit=lambda s, k, v: emits.append((s, k, v)), stop=SimpleStopToken())
    final = nerf_kit.run(ctx)

    raw = load_tiny_nerf_data()
    images, _ = _downsample(raw["images"], raw["focal"], cfg["downsample_factor"])
    test_img = images[-1]
    all_zero_baseline_psnr = _psnr(float(np.mean(test_img ** 2)))

    assert len(final["psnr_history"]) == 3
    assert final["final_test_psnr"] > all_zero_baseline_psnr + 2.0  # a real margin, not noise
    assert final["psnr_history"] == sorted(final["psnr_history"])  # real monotonic learning, not a fluke
    keys = {k for _, k, _ in emits}
    assert {"train_mse", "test_psnr"} <= keys


def test_nerf_kit_honours_stop():
    ctx = KitContext(
        job_id="t2",
        config={"downsample_factor": 10, "n_samples": 8, "iters": 10_000},
        emit=lambda s, k, v: None,
        stop=_AlwaysStop(),
    )
    final = nerf_kit.run(ctx)
    assert final["stopped_at_iter"] == 1


class _AlwaysStop:
    def is_set(self) -> bool:
        return True
