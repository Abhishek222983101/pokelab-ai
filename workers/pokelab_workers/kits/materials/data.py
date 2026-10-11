"""Loads the real "Superconductivty Data" set (Hamidieh et al. 2018,
UCI/OpenML id 44148, 21263 compounds x 81 physicochemical features ->
critical temperature). This is the same table Matbench-style materials
ML benchmarks regress on, fetched via sklearn's real OpenML client (not
synthesized) and cached locally by sklearn after the first pull.
"""
from __future__ import annotations

from sklearn.datasets import fetch_openml
from sklearn.model_selection import train_test_split

from pokelab_workers.kits.data_home import ensure_data_home

OPENML_DATA_ID = 44148


def load_split(seed: int, test_size: float = 0.2):
    bunch = fetch_openml(data_id=OPENML_DATA_ID, as_frame=False, parser="liac-arff", data_home=ensure_data_home())
    X, y = bunch.data, bunch.target.astype(float)
    return train_test_split(X, y, test_size=test_size, random_state=seed)
