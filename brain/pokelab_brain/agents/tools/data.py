"""`data.inspect` (§6.4.3): schema, row count, head, class balance for
CSV/Parquet/NPZ — an agent's one real look at a dataset before writing
code against it, without dumping the whole file into the LLM's context.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def inspect(path: str | Path, class_column: str | None = None, head_n: int = 5) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"error": f"no such file: {path}"}

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _inspect_dataframe(pd.read_csv(path), class_column, head_n)
    if suffix == ".parquet":
        return _inspect_dataframe(pd.read_parquet(path), class_column, head_n)
    if suffix == ".npz":
        return _inspect_npz(path, head_n)
    if suffix == ".gz" and path.name.endswith(".json.gz"):
        return _inspect_dataframe(pd.read_json(path, lines=False, compression="gzip"), class_column, head_n)
    return {"error": f"unsupported file type: {suffix}"}


def _inspect_dataframe(df: pd.DataFrame, class_column: str | None, head_n: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": "dataframe",
        "n_rows": len(df),
        "columns": {c: str(df[c].dtype) for c in df.columns},
        "head": df.head(head_n).to_dict(orient="records"),
    }
    if class_column and class_column in df.columns:
        counts = df[class_column].value_counts()
        result["class_balance"] = {str(k): int(v) for k, v in counts.items()}
    return result


def _inspect_npz(path: Path, head_n: int) -> dict[str, Any]:
    data = np.load(path)
    arrays = {}
    for key in data.files:
        arr = data[key]
        arrays[key] = {
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "head": arr.flat[: min(head_n, arr.size)].tolist(),
        }
    return {"kind": "npz", "arrays": arrays}
