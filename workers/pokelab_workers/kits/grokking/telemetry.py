"""The deeper grokking telemetry (P2.4): real signals computed on the
model's actual weights during training, not a post-hoc analysis script.

- embed_norm: L2 norm of the token embedding matrix. Nanda et al.
  observe this shrinking under weight decay as the model moves from a
  memorizing to a generalizing solution.
- embed_fourier_concentration: the famous result that grokked embeddings
  become sparse in frequency space (a handful of Fourier modes explain
  most of the embedding's variance) — this computes that concentration
  directly via a real FFT on the token axis, every eval.
"""
from __future__ import annotations

import torch


def embed_norm(model: torch.nn.Module) -> float:
    return float(model.embed.weight.detach().norm().item())


def embed_fourier_concentration(model: torch.nn.Module, p: int, top_k: int = 10) -> float:
    """FFT the embedding matrix along the token axis (the first p rows —
    row p is the '=' token and isn't part of the periodic structure), and
    return the fraction of total power in the top_k frequency components.
    A memorizing model's embedding looks like noise in frequency space
    (power spread thin); a grokked model's concentrates sharply — this is
    literally what Nanda et al. 2023 found by hand, computed live here."""
    with torch.no_grad():
        weight = model.embed.weight.detach()[:p].float()  # (p, d_model)
        spectrum = torch.fft.rfft(weight, dim=0)  # (p//2+1, d_model)
        power = (spectrum.abs() ** 2).sum(dim=1)  # (p//2+1,) power per frequency
        total = power.sum().item()
        if total <= 0:
            return 0.0
        top = torch.topk(power, min(top_k, power.numel())).values.sum().item()
        return float(top / total)
