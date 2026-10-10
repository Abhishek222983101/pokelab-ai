#!/usr/bin/env python
"""Item 4: PyTorch port of the official bmild/nerf tiny_nerf.ipynb (lego 100x100, tiny_nerf_data.npz).
Faithful to the notebook: D=8 x W=256 ReLU MLP (skip-concat of the input after layer 4, glorot init, zero bias),
positional encoding L (L=0 => raw xyz), N_samples=64 stratified samples in [2,6], Adam 5e-4, one random training
image (all 10k rays) per iteration, test view = images[101], PSNR on it every --eval_every iterations
(as in the notebook, iteration i is evaluated after its optimizer step, i.e. after i+1 steps).
Rays of the image are processed in chunks with gradient accumulation (same gradient as the full-image loss).
Afterwards: times rendering of 100x100 novel views on the notebook's 360-degree spiral (pose_spherical(th,-30,4)).
usage: tiny_nerf.py --data tiny_nerf_data.npz [--iters 1000] [--L 6] [--precision fp32|tf32|bf16]
Prints only `METRIC {json}` lines.
"""
import argparse
import json
import math
import os
import time

import numpy as np

T0 = time.perf_counter()
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402


def emit(step, **kw):
    print("METRIC " + json.dumps({"step": step, **kw, "wall_s": round(time.perf_counter() - T0, 3)}), flush=True)


def posenc(x, L):
    rets = [x]
    for i in range(L):
        rets += [torch.sin(2.0 ** i * x), torch.cos(2.0 ** i * x)]
    return torch.cat(rets, -1)


class TinyNeRF(nn.Module):
    def __init__(self, D=8, W=256, in_ch=39):
        super().__init__()
        self.layers, ch = nn.ModuleList(), in_ch
        for i in range(D):
            self.layers.append(nn.Linear(ch, W))
            ch = W + in_ch if (i % 4 == 0 and i > 0) else W
        self.out = nn.Linear(ch, 4)
        for m in self.modules():
            if isinstance(m, nn.Linear):  # Keras Dense defaults
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x):
        h = x
        for i, layer in enumerate(self.layers):
            h = F.relu(layer(h))
            if i % 4 == 0 and i > 0:
                h = torch.cat([h, x], -1)
        return self.out(h)


def get_rays(H, W, focal, c2w):
    dev = c2w.device
    i, j = torch.meshgrid(torch.arange(W, dtype=torch.float32, device=dev),
                          torch.arange(H, dtype=torch.float32, device=dev), indexing="xy")
    dirs = torch.stack([(i - W * .5) / focal, -(j - H * .5) / focal, -torch.ones_like(i)], -1)
    rays_d = (dirs[..., None, :] * c2w[:3, :3]).sum(-1)
    rays_o = c2w[:3, -1].expand(rays_d.shape)
    return rays_o.reshape(-1, 3), rays_d.reshape(-1, 3)


def render_rays(model, rays_o, rays_d, L, near=2., far=6., N=64, rand=False, amp=False):
    z = torch.linspace(near, far, N, device=rays_o.device).expand(rays_o.shape[0], N)
    if rand:
        z = z + torch.rand(rays_o.shape[0], N, device=rays_o.device) * (far - near) / N
    pts = rays_o[:, None, :] + rays_d[:, None, :] * z[..., None]
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        raw = model(posenc(pts.reshape(-1, 3), L))
    raw = raw.float().reshape(rays_o.shape[0], N, 4)
    sigma = F.relu(raw[..., 3])
    rgb = torch.sigmoid(raw[..., :3])
    dists = torch.cat([z[..., 1:] - z[..., :-1], torch.full_like(z[..., :1], 1e10)], -1)
    alpha = 1. - torch.exp(-sigma * dists)
    trans = torch.cumprod(torch.cat([torch.ones_like(alpha[..., :1]), 1. - alpha + 1e-10], -1), -1)[..., :-1]
    w = alpha * trans
    return (w[..., None] * rgb).sum(-2)


def render_image(model, H, W, focal, c2w, L, N, chunk, amp):
    rays_o, rays_d = get_rays(H, W, focal, c2w)
    with torch.no_grad():
        out = torch.cat([render_rays(model, rays_o[c:c + chunk], rays_d[c:c + chunk], L, N=N, amp=amp)
                         for c in range(0, rays_o.shape[0], chunk)], 0)
    return out.reshape(H, W, 3)


def pose_spherical(theta, phi, radius):
    trans_t = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, radius], [0, 0, 0, 1]], dtype=np.float32)
    ph, th = phi / 180. * np.pi, theta / 180. * np.pi
    rot_phi = np.array([[1, 0, 0, 0], [0, np.cos(ph), -np.sin(ph), 0], [0, np.sin(ph), np.cos(ph), 0], [0, 0, 0, 1]], dtype=np.float32)
    rot_theta = np.array([[np.cos(th), 0, -np.sin(th), 0], [0, 1, 0, 0], [np.sin(th), 0, np.cos(th), 0], [0, 0, 0, 1]], dtype=np.float32)
    c2w = rot_theta @ rot_phi @ trans_t
    return np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float32) @ c2w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--iters", type=int, default=1000)
    ap.add_argument("--L", type=int, default=6)
    ap.add_argument("--D", type=int, default=8)
    ap.add_argument("--W", type=int, default=256)
    ap.add_argument("--N_samples", type=int, default=64)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--eval_every", type=int, default=50)
    ap.add_argument("--chunk", type=int, default=5000, help="rays per grad-accumulation chunk")
    ap.add_argument("--precision", choices=["fp32", "tf32", "bf16"], default="tf32")
    ap.add_argument("--video_frames", type=int, default=120)
    ap.add_argument("--time_cap", type=float, default=600, help="stop training after this many train seconds")
    ap.add_argument("--save_frames", default="")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    torch.backends.cuda.matmul.allow_tf32 = a.precision == "tf32"
    torch.backends.cudnn.allow_tf32 = a.precision == "tf32"
    amp = a.precision == "bf16"
    dev = torch.device("cuda")
    d = np.load(a.data, allow_pickle=False)
    images, poses, focal = d["images"], d["poses"], float(d["focal"])
    H, W = images.shape[1:3]
    testimg = torch.tensor(images[101, ..., :3], device=dev)
    testpose = torch.tensor(poses[101], device=dev)
    imgs = torch.tensor(images[:100, ..., :3], device=dev)
    pss = torch.tensor(poses[:100], device=dev)
    emit("data", n_images=int(images.shape[0]), H=int(H), W=int(W), focal=round(focal, 3), train_views=100, test_view=101)
    model = TinyNeRF(a.D, a.W, 3 + 6 * a.L).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    emit("config", L=a.L, D=a.D, W=a.W, N_samples=a.N_samples, lr=a.lr, precision=a.precision, chunk=a.chunk,
         params=sum(p.numel() for p in model.parameters()), torch=torch.__version__)
    train_s = 0.0
    torch.cuda.reset_peak_memory_stats()
    for it in range(a.iters + 1):
        torch.cuda.synchronize()
        t = time.perf_counter()
        i = int(rng.integers(100))
        rays_o, rays_d = get_rays(H, W, focal, pss[i])
        target = imgs[i].reshape(-1, 3)
        n = rays_o.shape[0]
        opt.zero_grad(set_to_none=True)
        tot = 0.0
        for c in range(0, n, a.chunk):
            rgb = render_rays(model, rays_o[c:c + a.chunk], rays_d[c:c + a.chunk], a.L, N=a.N_samples, rand=True, amp=amp)
            loss = ((rgb - target[c:c + a.chunk]) ** 2).sum() / (n * 3)
            loss.backward()
            tot += loss.detach()
        opt.step()
        torch.cuda.synchronize()
        train_s += time.perf_counter() - t
        if it % a.eval_every == 0 or it == a.iters or train_s > a.time_cap:
            pred = render_image(model, H, W, focal, testpose, a.L, a.N_samples, 10000, amp)
            mse = F.mse_loss(pred, testimg).item()
            emit("eval", iter=it, train_loss=round(float(tot), 6), test_psnr=round(-10 * math.log10(mse), 3),
                 train_s=round(train_s, 2), ms_per_iter=round(1000 * train_s / (it + 1), 1))
        if train_s > a.time_cap:
            emit("time_cap_hit", iter=it, train_s=round(train_s, 2))
            break
    emit("train_done", iters_done=it + 1, train_s=round(train_s, 2),
         peak_vram_alloc_MiB=round(torch.cuda.max_memory_allocated() / 2**20),
         peak_vram_reserved_MiB=round(torch.cuda.max_memory_reserved() / 2**20))
    # novel-view rendering timing on the notebook's 360 spiral
    thetas = np.linspace(0., 360., 120, endpoint=False)[:a.video_frames]
    render_image(model, H, W, focal, torch.tensor(pose_spherical(0., -30., 4.), device=dev), a.L, a.N_samples, 10000, amp)
    times, frames = [], []
    for th in thetas:
        c2w = torch.tensor(pose_spherical(float(th), -30., 4.), device=dev)
        torch.cuda.synchronize()
        t = time.perf_counter()
        img = render_image(model, H, W, focal, c2w, a.L, a.N_samples, 10000, amp)
        torch.cuda.synchronize()
        times.append(time.perf_counter() - t)
        frames.append((img.clamp(0, 1) * 255).byte().cpu().numpy())
    emit("render", frames=len(times), H=int(H), W=int(W), N_samples=a.N_samples,
         ms_per_frame_mean=round(1000 * float(np.mean(times)), 1), ms_per_frame_min=round(1000 * float(np.min(times)), 1),
         ms_per_frame_max=round(1000 * float(np.max(times)), 1), total_render_s=round(float(np.sum(times)), 2))
    if a.save_frames:
        os.makedirs(os.path.dirname(os.path.abspath(a.save_frames)), exist_ok=True)
        np.save(a.save_frames, np.stack(frames))
        emit("saved", path=a.save_frames)


if __name__ == "__main__":
    main()
