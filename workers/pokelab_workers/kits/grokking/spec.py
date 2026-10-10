"""The `grokking` kit — reproduces Power et al. 2022 modular-addition
grokking (Nanda et al. 2023 config by default). Ported from
scripts/reference/grokbench/grok.py into the Kit interface so it runs
identically standalone (for benchmarking) and inside the warm pool.

W&B: offline by default (§11.6 — no API key reaches this process; only
`WANDB_MODE` does). labd syncs `var/wandb/` separately once a key is
available. Standalone runs (this file executed directly, or the
`POKELAB_WANDB_ONLINE=1` override) may log online for a quick check.
"""
from __future__ import annotations

import os
import time
from typing import Any

import torch
import torch.nn.functional as F

from pokelab_workers.kits.base import KitContext, register
from pokelab_workers.kits.grokking.models import MLP, Transformer

try:
    import wandb

    _HAS_WANDB = True
except ImportError:
    _HAS_WANDB = False


class GrokkingKit:
    name = "grokking"
    version = "1"

    def run(self, ctx: KitContext) -> dict[str, Any]:
        cfg = ctx.config
        model_name = cfg.get("model", "transformer")
        p = int(cfg.get("p", 113))
        frac = float(cfg.get("frac", 0.3))
        wd = float(cfg.get("wd", 1.0))
        lr = float(cfg.get("lr", 1e-3))
        beta2 = float(cfg.get("beta2", 0.98))
        steps = int(cfg.get("steps", 20000))
        seed = int(cfg.get("seed", 0))
        eval_every = int(cfg.get("eval_every", 100))
        d_hidden = int(cfg.get("d_hidden", 512))
        d_emb = int(cfg.get("d_emb", 128))
        stop_at = float(cfg.get("stop_at", 0.0))
        device_str = cfg.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
        device = torch.device(device_str)

        torch.manual_seed(seed)

        a = torch.arange(p).repeat_interleave(p)
        b = torch.arange(p).repeat(p)
        data = torch.stack([a, b, torch.full_like(a, p)], 1)
        labels = (a + b) % p
        g = torch.Generator().manual_seed(seed)
        perm = torch.randperm(p * p, generator=g)
        n_train = int(frac * p * p)
        tr, te = perm[:n_train], perm[n_train:]
        xtr, ytr = data[tr].to(device), labels[tr].to(device)
        xte, yte = data[te].to(device), labels[te].to(device)

        model = (Transformer(p) if model_name == "transformer" else MLP(p, d_emb, d_hidden)).to(device)
        fused = device.type == "cuda"
        opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd, betas=(0.9, beta2), fused=fused)

        run = None
        if _HAS_WANDB:
            mode = "online" if os.environ.get("POKELAB_WANDB_ONLINE") == "1" else os.environ.get("WANDB_MODE", "offline")
            run = wandb.init(
                project="pokelab",
                job_type="kit",
                group=cfg.get("project", "grokking-dev"),
                tags=["grokking", model_name, "live"],
                config={
                    "kit": "grokking", "model": model_name, "p": p, "frac": frac,
                    "wd": wd, "lr": lr, "beta2": beta2, "steps": steps, "seed": seed,
                },
                mode=mode,
                reinit="finish_previous",
            )

        def evaluate():
            with torch.no_grad():
                lt, le = model(xtr), model(xte)
                return (
                    F.cross_entropy(lt, ytr).item(),
                    (lt.argmax(-1) == ytr).float().mean().item(),
                    F.cross_entropy(le, yte).item(),
                    (le.argmax(-1) == yte).float().mean().item(),
                )

        t_train = time.perf_counter()
        last = {}
        step = 0
        for step in range(steps + 1):
            if ctx.stop.is_set():
                break
            if step % eval_every == 0 or step == steps:
                trl, tra, tel, tea = evaluate()
                last = {"train_acc": tra, "test_acc": tea, "train_loss": trl, "test_loss": tel}
                for key, value in last.items():
                    ctx.emit(step, key, value)
                if run is not None:
                    wandb.log({**last, "step": step})
                if stop_at and tea >= stop_at:
                    break
            if step == steps:
                break
            loss = F.cross_entropy(model(xtr), ytr)
            opt.zero_grad(set_to_none=False)
            loss.backward()
            opt.step()

        wall_s = time.perf_counter() - t_train
        final = {**last, "steps_run": step, "wall_s": wall_s, "device": str(device)}
        if run is not None:
            wandb.summary.update(final)
            run.finish()
        return final


kit = register(GrokkingKit())
