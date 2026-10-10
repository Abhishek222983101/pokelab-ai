#!/usr/bin/env python
"""Grokking on modular addition (a + b mod p), full-batch.

Models:
  transformer: Nanda et al. 2023 1-layer, d_model=128, 4 heads, d_mlp=512, no LayerNorm,
               input "a b =", predict from last position.
  mlp:         embed(a), embed(b) -> concat -> hidden (ReLU) -> logits.
Prints only `METRIC key=value ...` lines.
"""
import argparse
import time

T0 = time.perf_counter()
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

T_IMPORT = time.perf_counter() - T0


class Transformer(nn.Module):
    def __init__(self, p, d_model=128, n_heads=4, d_mlp=512, n_ctx=3):
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

    def forward(self, x):  # x: (B, 3)
        B, T = x.shape
        h = self.embed(x) + self.pos[:T]
        q, k, v = self.qkv(h).view(B, T, 3, self.n_heads, self.d_head).permute(2, 0, 3, 1, 4)
        # 1 layer + readout at last position only => only the last query / last-position MLP
        # affect the loss; computing just those is mathematically identical (and ~2-3x cheaper).
        q = q[:, :, -1:]  # (B, H, 1, dh); last position attends to all (causal mask is all-ones)
        att = ((q @ k.transpose(-1, -2)) / self.d_head**0.5).softmax(-1)
        z = (att @ v).reshape(B, -1)  # (B, H*dh)
        h = h[:, -1] + self.o(z)
        h = h + self.mlp_out(F.relu(self.mlp_in(h)))
        return self.unembed(h)


class MLP(nn.Module):
    def __init__(self, p, d_emb=128, d_hidden=512):
        super().__init__()
        self.embed = nn.Embedding(p + 1, d_emb)
        self.hidden = nn.Linear(2 * d_emb, d_hidden)
        self.out = nn.Linear(d_hidden, p)

    def forward(self, x):
        e = self.embed(x[:, :2]).flatten(1)
        return self.out(F.relu(self.hidden(e)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["transformer", "mlp"], default="transformer")
    ap.add_argument("--p", type=int, default=113)
    ap.add_argument("--frac", type=float, default=0.3)
    ap.add_argument("--wd", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--beta2", type=float, default=0.98)
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=0, help="torch CPU threads (0 = leave default)")
    ap.add_argument("--eval_every", type=int, default=100)
    ap.add_argument("--d_hidden", type=int, default=512)
    ap.add_argument("--d_emb", type=int, default=128)
    ap.add_argument("--grokfast", action="store_true")
    ap.add_argument("--gf_alpha", type=float, default=0.98)
    ap.add_argument("--gf_lamb", type=float, default=2.0)
    ap.add_argument("--fused", type=int, default=-1, help="fused AdamW (-1 = auto: on for cuda)")
    ap.add_argument("--flush_denormal", type=int, default=1)
    ap.add_argument("--tf32", action="store_true")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--stop_at", type=float, default=0.0, help="stop once test_acc >= this (0 = never)")
    args = ap.parse_args()

    if args.flush_denormal:
        torch.set_flush_denormal(True)  # CPU: avoid slow denormal math as weights/grads shrink
    if args.threads > 0:
        torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    dev = torch.device(args.device)

    p = args.p
    a = torch.arange(p).repeat_interleave(p)
    b = torch.arange(p).repeat(p)
    data = torch.stack([a, b, torch.full_like(a, p)], 1)
    labels = (a + b) % p
    g = torch.Generator().manual_seed(args.seed)
    perm = torch.randperm(p * p, generator=g)
    n_train = int(args.frac * p * p)
    tr, te = perm[:n_train], perm[n_train:]
    xtr, ytr = data[tr].to(dev), labels[tr].to(dev)
    xte, yte = data[te].to(dev), labels[te].to(dev)

    if args.model == "transformer":
        model = Transformer(p).to(dev)
    else:
        model = MLP(p, args.d_emb, args.d_hidden).to(dev)
    if args.tf32:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    fused = (dev.type == "cuda") if args.fused < 0 else bool(args.fused)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd,
                            betas=(0.9, args.beta2), fused=fused)
    fwd = torch.compile(model) if args.compile else model
    params = [q for q in model.parameters()]
    ema = [torch.zeros_like(q) for q in params] if args.grokfast else None

    def evaluate():
        with torch.no_grad():
            lt = model(xtr)
            le = model(xte)
            return (F.cross_entropy(lt, ytr).item(), (lt.argmax(-1) == ytr).float().mean().item(),
                    F.cross_entropy(le, yte).item(), (le.argmax(-1) == yte).float().mean().item())

    print(f"METRIC event=start import_s={T_IMPORT:.3f} setup_s={time.perf_counter()-T0:.3f} "
          f"device={dev} fused={fused} tf32={args.tf32} compile={args.compile} torch={torch.__version__} threads={torch.get_num_threads()} "
          f"n_train={n_train} n_test={len(te)} params={sum(q.numel() for q in params)}", flush=True)
    t_train = time.perf_counter()
    first_hit = {}
    for step in range(args.steps + 1):
        if step % args.eval_every == 0 or step == args.steps:
            trl, tra, tel, tea = evaluate()
            wall = time.perf_counter() - t_train
            print(f"METRIC step={step} train_acc={tra:.4f} test_acc={tea:.4f} train_loss={trl:.4f} "
                  f"test_loss={tel:.4f} wall_s={wall:.2f} since_launch_s={time.perf_counter()-T0:.2f}",
                  flush=True)
            for thr in (0.5, 0.95, 0.99):
                if tea >= thr and thr not in first_hit:
                    first_hit[thr] = (step, wall)
            if tra >= 0.99 and "train" not in first_hit:
                first_hit["train"] = (step, wall)
            if args.stop_at and tea >= args.stop_at:
                break
        if step == args.steps:
            break
        loss = F.cross_entropy(fwd(xtr), ytr)
        opt.zero_grad(set_to_none=False)
        loss.backward()
        if ema is not None:  # Grokfast-EMA (Lee et al. 2024)
            with torch.no_grad():
                for q, m in zip(params, ema):
                    m.mul_(args.gf_alpha).add_(q.grad, alpha=1 - args.gf_alpha)
                    q.grad.add_(m, alpha=args.gf_lamb)
        opt.step()
    wall = time.perf_counter() - t_train
    hit = lambda k: f"{first_hit[k][0]}" if k in first_hit else "NA"  # noqa: E731
    hits = lambda k: f"{first_hit[k][1]:.2f}" if k in first_hit else "NA"  # noqa: E731
    print(f"METRIC event=done steps_run={step} wall_s={wall:.2f} steps_per_s={step/max(wall,1e-9):.1f} "
          f"final_train_acc={tra:.4f} final_test_acc={tea:.4f} "
          f"train99_step={hit('train')} test50_step={hit(0.5)} test95_step={hit(0.95)} "
          f"test95_s={hits(0.95)} test99_step={hit(0.99)} total_since_launch_s={time.perf_counter()-T0:.2f}",
          flush=True)


if __name__ == "__main__":
    main()
