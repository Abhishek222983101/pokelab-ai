"""Notes & reports (§6.11): plain markdown files under `var/notes/<project>/`
— the console edits them as a textarea, every save is an event, but the
actual storage is just files (no new database, no special format, easy
to zip/export/print).
"""
from __future__ import annotations

import time
from pathlib import Path

KNOWN_NOTES = ("plan.md", "log.md", "results.md", "comparison.md", "lessons.md")


def notes_dir(var_dir: str | Path, project: str) -> Path:
    path = Path(var_dir) / "notes" / project
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_note(var_dir: str | Path, project: str, name: str, content: str) -> Path:
    path = notes_dir(var_dir, project) / name
    path.write_text(content)
    return path


def append_note(var_dir: str | Path, project: str, name: str, content: str, timestamped: bool = True) -> Path:
    """§6.11: plan.md is 'auto, revisions appended' — append rather than
    overwrite for the notes meant to accumulate a history."""
    path = notes_dir(var_dir, project) / name
    prefix = ""
    if timestamped:
        prefix = f"\n\n---\n*{time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
    with open(path, "a") as f:
        f.write(prefix + content)
    return path


def read_note(var_dir: str | Path, project: str, name: str) -> str | None:
    path = notes_dir(var_dir, project) / name
    if not path.exists():
        return None
    return path.read_text()


def list_notes(var_dir: str | Path, project: str) -> list[str]:
    path = notes_dir(var_dir, project)
    return sorted(p.name for p in path.glob("*.md"))
