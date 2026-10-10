import os

from pokelab_brain.agents.tools.data import inspect as inspect_data
from pokelab_brain.agents.tools.repo import inspect as inspect_repo

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABULAR_CSV = os.path.join(ROOT, "data", "raw", "tabular", "california.csv")
NERF_NPZ = os.path.join(ROOT, "data", "raw", "tiny_nerf", "tiny_nerf_data.npz")


def test_inspect_real_csv():
    if not os.path.exists(TABULAR_CSV):
        import pytest
        pytest.skip("california.csv not present")
    result = inspect_data(TABULAR_CSV, head_n=3)
    assert result["kind"] == "dataframe"
    assert result["n_rows"] > 0
    assert len(result["head"]) == 3
    assert len(result["columns"]) > 0


def test_inspect_real_npz():
    if not os.path.exists(NERF_NPZ):
        import pytest
        pytest.skip("tiny_nerf_data.npz not present")
    result = inspect_data(NERF_NPZ)
    assert result["kind"] == "npz"
    assert len(result["arrays"]) > 0
    for name, info in result["arrays"].items():
        assert "shape" in info and "dtype" in info


def test_inspect_missing_file():
    result = inspect_data("/no/such/file.csv")
    assert "error" in result


def test_inspect_local_repo_path():
    # inspect THIS repo's own brain/ directory — a real, local, existing tree
    result = inspect_repo(os.path.join(ROOT, "brain"), workspace_dir="/tmp/pokelab_workspace_test")
    assert "pyproject.toml" in result["tree"]
    assert result["readme_excerpt"] is None or isinstance(result["readme_excerpt"], str)


def test_inspect_missing_local_path():
    result = inspect_repo("/no/such/local/repo", workspace_dir="/tmp/pokelab_workspace_test")
    assert "error" in result


def test_inspect_real_remote_repo_clones_and_reads_readme(tmp_path):
    import pytest

    # a tiny, stable public repo — just enough to prove the clone path works
    result = inspect_repo("https://github.com/octocat/Hello-World", workspace_dir=tmp_path)
    if "error" in result:
        pytest.skip(f"network/git clone unavailable in this environment: {result['error']}")
    assert any("README" in t for t in result["tree"])
