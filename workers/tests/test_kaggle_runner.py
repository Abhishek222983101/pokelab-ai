"""_extract_protocol_lines is tested against a REAL downloaded Kaggle
kernel log (tests/fixtures/kaggle_real_log.json, captured from an actual
`kaggle kernels push` + `kernels output` run) — not a hand-written
fixture, because Kaggle's log wrapper format was itself the bug (see the
function's docstring). push_and_run's full round trip is exercised
manually (costs real Kaggle quota/time) rather than on every test run.
"""
import os

from pokelab_workers.remote.kaggle_runner import _extract_protocol_lines

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "kaggle_real_log.json")


def test_extracts_protocol_lines_from_a_real_kaggle_log():
    lines = _extract_protocol_lines(FIXTURE)
    kinds = [l["t"] for l in lines]
    assert kinds == ["ready", "metric", "metric", "metric", "done"]
    done = lines[-1]
    assert done["status"] == "ok"
    assert "Linux" in done["final"]["platform"]


def test_missing_log_file_returns_empty_list():
    assert _extract_protocol_lines("/no/such/file.json") == []
