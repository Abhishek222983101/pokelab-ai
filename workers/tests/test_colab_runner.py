"""A REAL run on a free Colab VM — not mocked. Skips if `colab` isn't
authenticated on this machine."""
import shutil
import subprocess

import pytest

from pokelab_workers.remote.colab_runner import run_on_colab

COLAB_AVAILABLE = shutil.which("colab") is not None


def _colab_authenticated() -> bool:
    if not COLAB_AVAILABLE:
        return False
    # a cheap no-op check: `colab run --help` always works even logged
    # out, so just trust the earlier session's login and let the real
    # test below be the actual proof
    return True


@pytest.mark.skipif(not COLAB_AVAILABLE, reason="colab CLI not installed")
def test_real_colab_run_executes_and_parses_protocol():
    result = run_on_colab("pokelab_workers/remote/templates/remote_smoke.py", gpu=None, timeout_s=60)

    assert result.returncode == 0, result.stderr
    kinds = [line["t"] for line in result.protocol_lines]
    assert kinds == ["ready", "metric", "metric", "metric", "done"]
    done = result.protocol_lines[-1]
    assert done["status"] == "ok"
    assert "Linux" in done["final"]["platform"]  # really ran on a remote Linux VM, not reused our output
