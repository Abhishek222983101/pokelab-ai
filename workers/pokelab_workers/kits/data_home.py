"""Where sklearn's OpenML client caches real downloaded datasets for
every kit that uses one (materials, distillation, arena). P12.1 (Doctor
complete): this used to default to sklearn's own global
`~/scikit_learn_data`, outside the project entirely and invisible to
`labd doctor` — moved here, inside workers/var/ (gitignored, same
pattern as nerf's tiny_nerf_data.npz and assets/gen/), so a single
directory check can actually tell you whether these real datasets are
cached.
"""
from __future__ import annotations

import os

DATA_HOME = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "var", "data", "sklearn_cache"))


def ensure_data_home() -> str:
    os.makedirs(DATA_HOME, exist_ok=True)
    return DATA_HOME
