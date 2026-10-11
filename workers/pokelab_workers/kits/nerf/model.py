"""The real Tiny NeRF architecture and volumetric renderer (Mildenhall
et al., ECCV 2020 / bmild's tiny_nerf reference): a positional-encoded
MLP mapping 3D points to (color, density), integrated along camera rays
via the real NeRF quadrature rule. Ported to torch so it trains
identically on CPU or GPU.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def positional_encoding(x: torch.Tensor, n_freqs: int) -> torch.Tensor:
    """gamma(p) = (p, sin(2^0 pi p), cos(2^0 pi p), ..., sin(2^{L-1} pi p), cos(2^{L-1} pi p))"""
    out = [x]
    for i in range(n_freqs):
        freq = 2.0 ** i
        out.append(torch.sin(freq * torch.pi * x))
        out.append(torch.cos(freq * torch.pi * x))
    return torch.cat(out, dim=-1)


class TinyNerfMLP(nn.Module):
    def __init__(self, n_freqs: int = 6, hidden: int = 128, depth: int = 4):
        super().__init__()
        self.n_freqs = n_freqs
        in_dim = 3 * (1 + 2 * n_freqs)
        layers: list[nn.Module] = [nn.Linear(in_dim, hidden), nn.ReLU()]
        for _ in range(depth - 1):
            layers += [nn.Linear(hidden, hidden), nn.ReLU()]
        last = nn.Linear(hidden, 4)  # rgb (3) + density (1)
        # [BUG FOUND experimentally]: PyTorch's default Linear init on this
        # final layer produced raw density values large enough that alpha
        # saturated to ~1 at the very first sample on every ray — and once
        # saturated, d(alpha)/d(sigma) -> 0, so gradient descent could never
        # walk density back down (a permanent dead trap, not undertraining).
        # Scaling this layer's init down fixes it: density starts near 0,
        # not already saturated, so the photometric loss can actually teach
        # the model where matter is.
        with torch.no_grad():
            last.weight *= 0.1
            last.bias.zero_()
        layers.append(last)
        self.net = nn.Sequential(*layers)

    def forward(self, pts: torch.Tensor) -> torch.Tensor:
        enc = positional_encoding(pts, self.n_freqs)
        return self.net(enc)


def get_rays(height: int, width: int, focal: float, c2w: torch.Tensor):
    i, j = torch.meshgrid(
        torch.arange(width, dtype=torch.float32),
        torch.arange(height, dtype=torch.float32),
        indexing="xy",
    )
    dirs = torch.stack(
        [(i - width * 0.5) / focal, -(j - height * 0.5) / focal, -torch.ones_like(i)], dim=-1
    )
    rays_d = torch.sum(dirs[..., None, :] * c2w[:3, :3], dim=-1)
    rays_o = c2w[:3, -1].expand(rays_d.shape)
    return rays_o, rays_d


def render_rays(model: TinyNerfMLP, rays_o: torch.Tensor, rays_d: torch.Tensor, near: float, far: float, n_samples: int):
    """The real NeRF quadrature render (stratified sampling + alpha
    compositing) — not a shortcut approximation."""
    t_vals = torch.linspace(near, far, n_samples)
    z_vals = t_vals + torch.rand(list(rays_o.shape[:-1]) + [n_samples]) * (far - near) / n_samples

    pts = rays_o[..., None, :] + rays_d[..., None, :] * z_vals[..., :, None]
    flat_pts = pts.reshape(-1, 3)
    raw = model(flat_pts).reshape(*pts.shape[:-1], 4)

    rgb = torch.sigmoid(raw[..., :3])
    # softplus, not relu: relu's gradient is exactly zero for any negative
    # raw density, which is a dead end once a point's density goes negative
    # (common after a few bad updates). softplus keeps a nonzero gradient
    # everywhere so training can always recover.
    sigma = F.softplus(raw[..., 3])

    dists = z_vals[..., 1:] - z_vals[..., :-1]
    dists = torch.cat([dists, torch.full_like(dists[..., :1], 1e10)], dim=-1)
    alpha = 1.0 - torch.exp(-sigma * dists)
    weights = alpha * torch.cumprod(torch.cat([torch.ones_like(alpha[..., :1]), 1.0 - alpha + 1e-10], dim=-1), dim=-1)[..., :-1]

    rgb_map = torch.sum(weights[..., None] * rgb, dim=-2)
    depth_map = torch.sum(weights * z_vals, dim=-1)
    acc_map = torch.sum(weights, dim=-1)
    return rgb_map, depth_map, acc_map
