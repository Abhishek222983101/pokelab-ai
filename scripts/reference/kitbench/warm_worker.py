#!/usr/bin/env python
"""Long-lived GPU worker: imports torch + initialises CUDA once, then reads one JSON job per stdin line
and runs a tiny full-batch training loop (grok MLP / Nanda transformer on a+b mod p).

usage: warm_worker.py [--prewarm]      (stdin: one JSON job per line, e.g. {"id":1,"model":"mlp","steps":300})
Prints only `METRIC {json}` lines. Every line carries wall_s = seconds since process start.
"""
import json
import os
import sys
import time

T0 = time.perf_counter()
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

T_IMPORT = time.perf_counter() - T0


def emit(step, **kw):
    kw = {"step": step, **kw, "wall_s": round(time.perf_counter() - T0, 4)}
    print("METRIC " + json.dumps(kw), flush=True)


class MLP(nn.Module):
    def __init__(self, p, d_emb=128, d_hidden=512):
        super().__init__()
        self.embed = nn.Embedding(p + 1, d_emb)
        self.hidden = nn.Linear(2 * d_emb, d_hidden)
        self.out = nn.Linear(d_hidden, p)

    def forward(self, x):
        return self.out(F.relu(self.hidden(self.embed(x[:, :2]).flatten(1))))


def run_job(job):
    """Build data + model + optimiser on the GPU and train; report receipt -> first step latency."""
    t_recv = time.perf_counter()
    p, frac, steps = job.get("p", 113), job.get("frac", 0.3), job.get("steps", 300)
    torch.manual_seed(job.get("seed", 0))
    dev = torch.device("cuda")
    a = torch.arange(p).repeat_interleave(p)
    b = torch.arange(p).repeat(p)
    data = torch.stack([a, b, torch.full_like(a, p)], 1)
    labels = (a + b) % p
    perm = torch.randperm(p * p, generator=torch.Generator().manual_seed(job.get("seed", 0)))
    n_train = int(frac * p * p)
    xtr, ytr = data[perm[:n_train]].to(dev), labels[perm[:n_train]].to(dev)
    model = MLP(p, job.get("d_emb", 128), job.get("d_hidden", 512)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=job.get("lr", 3e-3), weight_decay=job.get("wd", 1.0),
                            betas=(0.9, 0.98), fused=True)
    torch.cuda.synchronize()
    t_built = time.perf_counter()
    for i in range(steps):
        loss = F.cross_entropy(model(xtr), ytr)
        opt.zero_grad(set_to_none=False)
        loss.backward()
        opt.step()
        if i == 0:
            torch.cuda.synchronize()
            t_first = time.perf_counter()
            emit("first_step", job=job.get("id"), recv_to_build_s=round(t_built - t_recv, 4),
                 recv_to_first_step_s=round(t_first - t_recv, 4), loss=round(loss.item(), 4))
    torch.cuda.synchronize()
    t_end = time.perf_counter()
    emit("job_done", job=job.get("id"), steps=steps, loss=round(loss.item(), 4),
         steps_per_s_after_first=round((steps - 1) / max(t_end - t_first, 1e-9), 1),
         recv_to_done_s=round(t_end - t_recv, 4))


def main():
    prewarm = "--prewarm" in sys.argv
    t = time.perf_counter()
    torch.zeros(1, device="cuda")
    torch.cuda.synchronize()
    t_cuda = time.perf_counter() - t
    t = time.perf_counter()
    if prewarm:  # touch every kernel the job uses (lazy CUDA module loading, cuBLAS handle, fused AdamW)
        run_job({"id": "prewarm", "steps": 3})
    emit("ready", pid=os.getpid(), import_s=round(T_IMPORT, 4), cuda_init_s=round(t_cuda, 4),
         prewarm=prewarm, prewarm_s=round(time.perf_counter() - t, 4), torch=torch.__version__)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        job = json.loads(line)
        if job.get("cmd") == "exit":
            break
        run_job(job)


if __name__ == "__main__":
    main()
