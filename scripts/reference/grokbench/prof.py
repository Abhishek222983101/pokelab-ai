"""Profile one training step on CPU. usage: M=transformer|mlp T=threads python prof.py"""
import importlib.util
import os
import sys

import torch
import torch.nn.functional as F
from torch.profiler import profile

spec = importlib.util.spec_from_file_location("g", os.path.join(os.path.dirname(__file__), "grok.py"))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
torch.set_num_threads(int(os.environ.get("T", 6)))
p = 113
m = g.Transformer(p) if os.environ.get("M", "transformer") == "transformer" else g.MLP(p)
x = torch.randint(0, p, (3830, 3))
y = torch.randint(0, p, (3830,))
opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1.0)


def step():
    loss = F.cross_entropy(m(x), y)
    opt.zero_grad()
    loss.backward()
    opt.step()


for _ in range(3):
    step()
with profile() as pr:
    for _ in range(5):
        step()
print(pr.key_averages().table(sort_by="self_cpu_time_total", row_limit=14))
