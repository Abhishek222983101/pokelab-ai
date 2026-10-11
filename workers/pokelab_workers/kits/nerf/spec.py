"""The `nerf` kit (P11.2, "3D") — reproduces the real Tiny NeRF training
loop (Mildenhall et al. ECCV 2020, bmild's reduced notebook version) on
the real 106-view lego-bulldozer dataset. Trains a positional-encoded
MLP via gradient descent against real pixel-reconstruction loss and
reports PSNR on a held-out test view, exactly like the paper's own
evaluation protocol. CPU-capable at reduced resolution/sample count by
design (§P11 scope note: full 100x100/64-sample/1000-iter runs are a
GPU-minutes job; the automated test uses a tiny CPU-fast config to
prove the real math, same pattern as the grokking kit's CPU smoke test).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from pokelab_workers.kits.base import KitContext, register
from pokelab_workers.kits.nerf.data import load_tiny_nerf_data
from pokelab_workers.kits.nerf.model import TinyNerfMLP, get_rays, render_rays


def _downsample(images: np.ndarray, focal: float, factor: int) -> tuple[np.ndarray, float]:
    if factor == 1:
        return images, focal
    n, h, w, c = images.shape
    assert h % factor == 0 and w % factor == 0, f"image size {h}x{w} not divisible by {factor}"
    reshaped = images.reshape(n, h // factor, factor, w // factor, factor, c)
    return reshaped.mean(axis=(2, 4)), focal / factor


def _psnr(mse: float) -> float:
    return -10.0 * math.log10(max(mse, 1e-10))


class NerfKit:
    name = "nerf"
    version = "1"

    def run(self, ctx: KitContext) -> dict[str, Any]:
        cfg = ctx.config
        seed = int(cfg.get("seed", 0))
        torch.manual_seed(seed)

        downsample_factor = int(cfg.get("downsample_factor", 4))  # 100 -> 25px by default (CPU-fast)
        n_samples = int(cfg.get("n_samples", 32))
        iters = int(cfg.get("iters", 200))
        lr = float(cfg.get("lr", 5e-3))
        n_freqs = int(cfg.get("n_freqs", 6))
        hidden = int(cfg.get("hidden", 128))
        test_every = int(cfg.get("test_every", 20))
        near, far = 2.0, 6.0

        raw = load_tiny_nerf_data()
        images, focal = _downsample(raw["images"], raw["focal"], downsample_factor)
        poses = raw["poses"]
        h, w = images.shape[1], images.shape[2]

        images_t = torch.tensor(images, dtype=torch.float32)
        poses_t = torch.tensor(poses, dtype=torch.float32)

        test_idx = images_t.shape[0] - 1  # the same held-out convention as the reference notebook
        train_idx = list(range(test_idx))

        model = TinyNerfMLP(n_freqs=n_freqs, hidden=hidden)
        opt = torch.optim.Adam(model.parameters(), lr=lr)

        psnr_history: list[float] = []
        for step in range(1, iters + 1):
            if ctx.stop.is_set():
                return {"stopped_at_iter": step, "psnr_history": psnr_history}

            img_i = train_idx[torch.randint(0, len(train_idx), (1,)).item()]
            target = images_t[img_i]
            c2w = poses_t[img_i]
            rays_o, rays_d = get_rays(h, w, focal, c2w)
            rgb_pred, _, _ = render_rays(model, rays_o, rays_d, near, far, n_samples)

            loss = F.mse_loss(rgb_pred, target)
            opt.zero_grad()
            loss.backward()
            opt.step()

            ctx.emit(step, "train_mse", float(loss.item()))

            if step % test_every == 0 or step == iters:
                with torch.no_grad():
                    test_c2w = poses_t[test_idx]
                    rays_o_t, rays_d_t = get_rays(h, w, focal, test_c2w)
                    rgb_test, _, _ = render_rays(model, rays_o_t, rays_d_t, near, far, n_samples)
                    test_mse = float(F.mse_loss(rgb_test, images_t[test_idx]).item())
                psnr = _psnr(test_mse)
                psnr_history.append(psnr)
                ctx.emit(step, "test_psnr", psnr)

        return {
            "iters": iters,
            "final_test_psnr": psnr_history[-1] if psnr_history else None,
            "psnr_history": psnr_history,
            "image_size": [h, w],
            "n_samples_per_ray": n_samples,
        }


kit = register(NerfKit())
