"""A tiny, fast, CPU-only run of the real grokking kit — proves the ported
model/training loop works, without waiting for a full grok (which needs GPU
and tens of seconds minimum). Full-size runs are exercised manually / by
`scripts/reference/grokbench` and reported in docs with [MEASURED] numbers.
"""
import os

os.environ.setdefault("WANDB_MODE", "disabled")  # no network, no local run dir in CI

from pokelab_workers.kits.base import KitContext, SimpleStopToken
from pokelab_workers.kits.grokking.spec import kit as grokking_kit


def test_grokking_kit_runs_a_few_steps_on_cpu():
    metrics_seen = []

    def emit(step, key, value):
        metrics_seen.append((step, key, value))

    ctx = KitContext(
        job_id="t1",
        config={
            "model": "mlp",  # cheaper than the transformer for a smoke test
            "p": 17,
            "frac": 0.5,
            "steps": 20,
            "eval_every": 10,
            "device": "cpu",
            "d_hidden": 32,
            "d_emb": 16,
        },
        emit=emit,
        stop=SimpleStopToken(),
    )
    final = grokking_kit.run(ctx)

    assert "train_acc" in final and "test_acc" in final
    assert final["steps_run"] == 20
    assert final["device"] == "cpu"
    keys = {k for _, k, _ in metrics_seen}
    assert {"train_acc", "test_acc", "train_loss", "test_loss"} <= keys
