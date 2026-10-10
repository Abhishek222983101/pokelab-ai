"""`repo.inspect` (§6.4.3): tree, README, entry points for a local path
or a git URL (cloned `--depth 1` into the project workspace — a shallow
clone is enough to look around, and keeps this fast and small).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

_ENTRY_POINT_NAMES = {"main.py", "app.py", "run.py", "train.py", "__main__.py", "cli.py"}


def inspect(path_or_url: str, workspace_dir: str | Path, max_tree_entries: int = 200) -> dict[str, Any]:
    if path_or_url.startswith(("http://", "https://", "git@")):
        local_path = _clone(path_or_url, workspace_dir)
        if local_path is None:
            return {"error": f"git clone failed for {path_or_url}"}
    else:
        local_path = Path(path_or_url)
        if not local_path.exists():
            return {"error": f"no such path: {path_or_url}"}

    skip_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "wandb", ".pytest_cache", "target"}
    tree = []
    for p in sorted(local_path.rglob("*")):
        if any(part in skip_dirs or part.startswith(".git") for part in p.parts):
            continue
        tree.append(str(p.relative_to(local_path)))
        if len(tree) >= max_tree_entries:
            break

    readme = None
    for name in ("README.md", "readme.md", "README.rst", "README"):
        candidate = local_path / name
        if candidate.exists():
            readme = candidate.read_text(errors="replace")[:3000]
            break

    entry_points = [t for t in tree if Path(t).name in _ENTRY_POINT_NAMES]

    return {
        "path": str(local_path),
        "tree": tree,
        "readme_excerpt": readme,
        "entry_points": entry_points,
    }


def _clone(url: str, workspace_dir: str | Path) -> Path | None:
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    dest = workspace_dir / name
    if dest.exists():
        return dest
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return None
    return dest
