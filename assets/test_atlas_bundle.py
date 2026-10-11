"""Checks on the generated asset bundle (web/public/assets/gen/).

Runs against whatever `python3 assets/build_atlases.py` last produced
(builds it first if manifest.json is absent).

    python3 -m pytest assets/test_atlas_bundle.py     # if pytest is installed
    python3 assets/test_atlas_bundle.py                # plain asserts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_atlases  # noqa: E402

OUT = build_atlases.OUT
PUBLIC = build_atlases.PUBLIC
BUDGET_BYTES = 15 * 1024 * 1024  # §9.9


def _manifest() -> dict:
    mf = OUT / "manifest.json"
    if not mf.exists():
        build_atlases.build()
    return json.loads(mf.read_text())


def _manifest_paths(node) -> list[str]:
    """Every string in the manifest that looks like an asset path."""
    if isinstance(node, dict):
        return [p for v in node.values() for p in _manifest_paths(v)]
    if isinstance(node, list):
        return [p for v in node for p in _manifest_paths(v)]
    if isinstance(node, str) and node.startswith("assets/gen/"):
        return [node]
    return []


def test_every_manifest_path_exists():
    m = _manifest()
    paths = _manifest_paths({k: v for k, v in m.items() if k != "missing"})
    assert paths, "manifest lists no assets"
    for p in paths:
        assert not p.startswith("/"), p
        assert (PUBLIC / p).is_file(), f"manifest path missing on disk: {p}"


def test_every_atlas_frame_lies_inside_its_png():
    jsons = sorted(OUT.glob("*/*.json"))
    assert jsons, "no atlas JSON generated"
    for jf in jsons:
        atlas = json.loads(jf.read_text())
        png = jf.with_name(atlas["meta"]["image"])
        assert png.is_file(), f"{jf.name}: image {png.name} missing"
        with Image.open(png) as im:
            W, H = im.size
            assert im.mode == "RGBA", f"{png.name} is {im.mode}"
        assert atlas["meta"]["size"] == {"w": W, "h": H}, jf.name
        assert atlas["frames"], f"{jf.name}: no frames"
        for key, fr in atlas["frames"].items():
            r = fr["frame"]
            assert r["w"] > 0 and r["h"] > 0, f"{jf.name}:{key} empty rect"
            assert 0 <= r["x"] and 0 <= r["y"], f"{jf.name}:{key} negative origin"
            assert r["x"] + r["w"] <= W and r["y"] + r["h"] <= H, \
                f"{jf.name}:{key} rect {r} outside {W}x{H}"
            assert isinstance(fr["duration"], int) and fr["duration"] > 0, f"{jf.name}:{key}"
        for name, a in atlas.get("anims", {}).items():
            for k in a["frames"]:
                assert k in atlas["frames"], f"{jf.name}: anim {name} -> unknown frame {k}"


def test_walk_atlases_have_four_directions_and_transparency():
    m = _manifest()
    for name, w in m["walk"].items():
        atlas = json.loads((PUBLIC / w["json"]).read_text())
        for d in ("down", "right", "up", "left"):
            assert f"walk_{d}_0" in atlas["frames"], f"{name}: no walk_{d}_0"
        with Image.open(PUBLIC / w["png"]) as im:
            assert im.getpixel((0, 0))[3] == 0 or im.getchannel("A").getextrema()[0] == 0, \
                f"{name}: walk sheet has no transparency"


def test_people_have_baked_right_frames_and_transparent_bg():
    m = _manifest()
    for name, p in m["people"].items():
        atlas = json.loads((PUBLIC / p["json"]).read_text())
        for d in ("down", "up", "left", "right"):
            for pose in ("idle", "walk1", "walk2"):
                assert f"{d}_{pose}" in atlas["frames"], f"{name}: {d}_{pose}"
        with Image.open(PUBLIC / p["png"]) as im:
            r = atlas["frames"]["down_idle"]["frame"]
            assert (r["w"], r["h"]) == (16, 32)
            assert im.getpixel((r["x"], r["y"]))[3] == 0, f"{name}: corner not transparent"
            l = atlas["frames"]["left_idle"]["frame"]
            rr = atlas["frames"]["right_idle"]["frame"]
            left = im.crop((l["x"], l["y"], l["x"] + 16, l["y"] + 32))
            right = im.crop((rr["x"], rr["y"], rr["x"] + 16, rr["y"] + 32))
            assert left.transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes() == \
                right.tobytes(), f"{name}: right_idle is not mirrored left_idle"


def test_bundle_under_budget():
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    assert total < BUDGET_BYTES, f"{total / 1e6:.1f} MB exceeds budget"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed")
