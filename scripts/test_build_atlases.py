"""Real test for assets/build_atlases.py — runs the actual function
against the real roster.toml and real Showdown sprite files on disk."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "assets"))
import build_atlases  # noqa: E402


def test_manifest_includes_eevee_and_both_trainers():
    manifest = build_atlases.build()
    assert "eevee" in manifest["mons"]
    assert "ash" in manifest["trainers"]
    assert "oak" in manifest["trainers"]
    assert not manifest.get("missing"), f"unexpectedly missing: {manifest.get('missing')}"


def test_copied_files_actually_exist_on_disk():
    build_atlases.build()
    out = build_atlases.OUT
    assert (out / "battle" / "eevee_front_static.png").exists()
    assert (out / "battle" / "eevee_back_static.png").exists()
    assert (out / "trainers" / "ash.png").exists()
    assert (out / "trainers" / "oak.png").exists()
    assert (out / "manifest.json").exists()


def test_manifest_json_is_valid_and_matches_files_on_disk():
    manifest = build_atlases.build()
    with open(build_atlases.OUT / "manifest.json") as f:
        on_disk = json.load(f)
    assert on_disk == manifest
    for species, paths in manifest["mons"].items():
        assert (build_atlases.ROOT / "web" / "public" / paths["front"]).exists()
        assert (build_atlases.ROOT / "web" / "public" / paths["back"]).exists()
