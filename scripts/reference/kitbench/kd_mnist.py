#!/usr/bin/env python
"""Item 3: Hinton et al. 2015 knowledge distillation on MNIST (minimal reimplementation).
MNIST idx.gz files are loaded once into GPU tensors; minibatches are index slices (no DataLoader).
 teacher : 784-1200-1200-10, ReLU, dropout (0.2 input / 0.5 hidden), Adam
 student : configurable hidden sizes, no dropout; (a) hard labels, (b) KD with temperature T, weight alpha on
           the soft loss (scaled by T^2 as in the paper) and (1-alpha) on the hard loss. Teacher logits are
           precomputed once (teacher in eval mode).
Reports test errors out of 10,000 after every epoch and wall-clock per phase.
usage: kd_mnist.py --data DIR [--teacher_epochs 10] [--student 800,800] [--student_epochs 10] [--temps 1,4,20]
Prints only `METRIC {json}` lines.
"""
import argparse
import gzip
import json
import os
import time

import numpy as np

T0 = time.perf_counter()
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402


def emit(step, **kw):
    print("METRIC " + json.dumps({"step": step, **kw, "wall_s": round(time.perf_counter() - T0, 3)}), flush=True)


def load_idx(path):
    with gzip.open(path, "rb") as f:
        raw = f.read()
    magic = int.from_bytes(raw[0:4], "big")
    ndim = magic & 0xFF
    dims = [int.from_bytes(raw[4 + 4 * i: 8 + 4 * i], "big") for i in range(ndim)]
    return np.frombuffer(raw, dtype=np.uint8, offset=4 + 4 * ndim).reshape(dims)


def mlp(sizes, p_in=0.0, p_hid=0.0):
    layers = [nn.Dropout(p_in)] if p_in else []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:
            layers.append(nn.ReLU())
            if p_hid:
                layers.append(nn.Dropout(p_hid))
    return nn.Sequential(*layers)


def test_errors(model, X, Y):
    model.eval()
    with torch.no_grad():
        err = int((model(X).argmax(1) != Y).sum().item())
    model.train()
    return err


def train(name, model, Xtr, Ytr, Xte, Yte, epochs, bs, lr, soft=None, T=1.0, alpha=0.0, seed=0):
    """soft: precomputed teacher logits for the training set (KD) or None (hard labels)."""
    torch.manual_seed(seed)
    opt = torch.optim.Adam(model.parameters(), lr=lr, fused=True)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs * ((len(Xtr) + bs - 1) // bs))
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    errs = []
    for ep in range(epochs):
        perm = torch.randperm(len(Xtr), device=Xtr.device)
        for i in range(0, len(Xtr), bs):
            idx = perm[i:i + bs]
            out = model(Xtr[idx])
            hard = F.cross_entropy(out, Ytr[idx])
            if soft is None:
                loss = hard
            else:
                p_t = F.softmax(soft[idx] / T, 1)
                kd = F.kl_div(F.log_softmax(out / T, 1), p_t, reduction="batchmean") * (T * T)
                loss = alpha * kd + (1 - alpha) * hard
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
        e = test_errors(model, Xte, Yte)
        errs.append(e)
        torch.cuda.synchronize()
        emit("epoch", phase=name, epoch=ep + 1, test_errors=e, phase_wall_s=round(time.perf_counter() - t0, 2))
    torch.cuda.synchronize()
    wall = time.perf_counter() - t0
    emit("phase_done", phase=name, T=T if soft is not None else None, alpha=alpha if soft is not None else None,
         epochs=epochs, final_test_errors=errs[-1], best_test_errors=min(errs), phase_wall_s=round(wall, 2))
    return errs[-1], wall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--teacher_epochs", type=int, default=10)
    ap.add_argument("--student", default="800,800")
    ap.add_argument("--student_epochs", type=int, default=10)
    ap.add_argument("--temps", default="1,4,20")
    ap.add_argument("--alpha", type=float, default=0.9)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save_teacher", default="")
    ap.add_argument("--load_teacher", default="")
    a = ap.parse_args()
    dev = torch.device("cuda")
    t = time.perf_counter()
    Xtr = torch.tensor(load_idx(os.path.join(a.data, "train-images-idx3-ubyte.gz")).reshape(-1, 784), device=dev).float() / 255
    Ytr = torch.tensor(load_idx(os.path.join(a.data, "train-labels-idx1-ubyte.gz")), device=dev).long()
    Xte = torch.tensor(load_idx(os.path.join(a.data, "t10k-images-idx3-ubyte.gz")).reshape(-1, 784), device=dev).float() / 255
    Yte = torch.tensor(load_idx(os.path.join(a.data, "t10k-labels-idx1-ubyte.gz")), device=dev).long()
    torch.cuda.synchronize()
    emit("data_loaded", n_train=len(Xtr), n_test=len(Xte), load_s=round(time.perf_counter() - t, 3),
         torch=torch.__version__)

    torch.manual_seed(a.seed)
    teacher = mlp([784, 1200, 1200, 10], p_in=0.2, p_hid=0.5).to(dev)
    if a.load_teacher:
        teacher.load_state_dict(torch.load(a.load_teacher, map_location=dev, weights_only=True))
        emit("teacher_loaded", test_errors=test_errors(teacher, Xte, Yte))
    else:
        train("teacher", teacher, Xtr, Ytr, Xte, Yte, a.teacher_epochs, a.bs, a.lr, seed=a.seed)
        if a.save_teacher:
            torch.save(teacher.state_dict(), a.save_teacher)
    teacher.eval()
    with torch.no_grad():
        soft = teacher(Xtr)
    hs = [int(x) for x in a.student.split(",") if x]
    sizes = [784] + hs + [10]
    torch.manual_seed(a.seed + 1)
    init = mlp(sizes).to(dev).state_dict()  # identical init for every student run
    emit("student_cfg", sizes=sizes, params=sum(v.numel() for v in init.values()), alpha=a.alpha,
         epochs=a.student_epochs, bs=a.bs, lr=a.lr)
    res = {}
    s = mlp(sizes).to(dev)
    s.load_state_dict(init)
    res["hard"], _ = train("student_hard", s, Xtr, Ytr, Xte, Yte, a.student_epochs, a.bs, a.lr, seed=a.seed + 2)
    for T in [float(x) for x in a.temps.split(",") if x]:
        s = mlp(sizes).to(dev)
        s.load_state_dict(init)
        res[f"kd_T{T:g}"], _ = train(f"student_kd_T{T:g}", s, Xtr, Ytr, Xte, Yte, a.student_epochs, a.bs, a.lr,
                                     soft=soft, T=T, alpha=a.alpha, seed=a.seed + 2)
    emit("summary", student=sizes, test_errors=res, peak_vram_alloc_MiB=round(torch.cuda.max_memory_allocated() / 2**20),
         peak_vram_reserved_MiB=round(torch.cuda.max_memory_reserved() / 2**20))


if __name__ == "__main__":
    main()
