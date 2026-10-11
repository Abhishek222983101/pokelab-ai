"""Real tabular datasets for the comparison arena (P11.4) — the same
family Grinsztajn et al. 2022 ("Why do tree-based models still
outperform deep learning on tabular data?") benchmark against: two real
OpenML tables (MagicTelescope id 1120, Electricity id 151), fetched via
sklearn's real OpenML client, not synthesized.
"""
from __future__ import annotations

import numpy as np
from sklearn.datasets import fetch_openml

DATASETS = {
    "magictelescope": 1120,
    "electricity": 151,
}


def load_dataset(name: str):
    if name not in DATASETS:
        raise KeyError(f"unknown arena dataset {name!r}; known: {sorted(DATASETS)}")
    bunch = fetch_openml(data_id=DATASETS[name], as_frame=False, parser="liac-arff")
    X = bunch.data.astype(np.float64)
    y = (bunch.target == np.unique(bunch.target)[0]).astype(int)
    return X, y
