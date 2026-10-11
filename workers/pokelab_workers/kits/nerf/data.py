"""Fetches the real "Tiny NeRF" lego-bulldozer dataset (106 x 100x100
RGB renders + camera poses + focal length) — the same data the original
bmild Tiny NeRF notebook trains on, a reduced-resolution subset of the
full NeRF synthetic Lego scene (Mildenhall et al., ECCV 2020). Cached in
var/data/ (gitignored, like assets/gen) so it's only ever pulled once.
"""
from __future__ import annotations

import os
import urllib.request

import numpy as np

_URL = "https://cseweb.ucsd.edu/~viscomp/projects/LF/papers/ECCV20/nerf/tiny_nerf_data.npz"
_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "var", "data", "tiny_nerf_data.npz")


def load_tiny_nerf_data() -> dict[str, np.ndarray]:
    path = os.path.abspath(_CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        urllib.request.urlretrieve(_URL, path)  # noqa: S310 - fixed, known-good research dataset URL
    data = np.load(path)
    return {"images": data["images"], "poses": data["poses"], "focal": float(data["focal"])}
