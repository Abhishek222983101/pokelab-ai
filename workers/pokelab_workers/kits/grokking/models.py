"""Models for the grokking kit — ported from scripts/reference/grokbench/grok.py
(Nanda et al. 2023 1-layer transformer; a plain MLP baseline for what-ifs).
No behaviour changed from the reference; only wrapped for reuse."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class Transformer(nn.Module):
    def __init__(self, p: int, d_model: int = 128, n_heads: int = 4, d_mlp: int = 512, n_ctx: int = 3):
        super().__init__()
        self.n_heads, self.d_head = n_heads, d_model // n_heads
        self.embed = nn.Embedding(p + 1, d_model)  # token p is "="
        self.pos = nn.Parameter(torch.randn(n_ctx, d_model) / d_model**0.5)
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.o = nn.Linear(d_model, d_model, bias=False)
        self.mlp_in = nn.Linear(d_model, d_mlp)
        self.mlp_out = nn.Linear(d_mlp, d_model)
        self.unembed = nn.Linear(d_model, p, bias=False)
        self.register_buffer("mask", torch.tril(torch.ones(n_ctx, n_ctx, dtype=torch.bool)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t = x.shape
        h = self.embed(x) + self.pos[:t]
        q, k, v = self.qkv(h).view(b, t, 3, self.n_heads, self.d_head).permute(2, 0, 3, 1, 4)
        q = q[:, :, -1:]
        att = ((q @ k.transpose(-1, -2)) / self.d_head**0.5).softmax(-1)
        z = (att @ v).reshape(b, -1)
        h = h[:, -1] + self.o(z)
        h = h + self.mlp_out(F.relu(self.mlp_in(h)))
        return self.unembed(h)


class MLP(nn.Module):
    def __init__(self, p: int, d_emb: int = 128, d_hidden: int = 512):
        super().__init__()
        self.embed = nn.Embedding(p + 1, d_emb)
        self.hidden = nn.Linear(2 * d_emb, d_hidden)
        self.out = nn.Linear(d_hidden, p)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e = self.embed(x[:, :2]).flatten(1)
        return self.out(F.relu(self.hidden(e)))
