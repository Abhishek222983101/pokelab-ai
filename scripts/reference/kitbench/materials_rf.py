#!/usr/bin/env python
"""Item 5: matbench composition-only regression on CPU.
Loads matbench_<name>.json.gz (pandas split-orient JSON: columns [composition, target]).
Featurisation:
  frac   : element-fraction vector (own formula parser, handles parentheses + fractional amounts)
  magpie : matminer ElementProperty.from_preset("magpie") on pymatgen Composition (only with --magpie; needs matminer)
Model: sklearn RandomForestRegressor, 5-fold KFold(shuffle, random_state=18012019 as in matbench), MAE.
Also a mean-predictor (dummy) MAE on the same folds.
usage: materials_rf.py --file X.json.gz [--magpie] [--trees 500] [--jobs 8]
Prints only `METRIC {json}` lines.
"""
import argparse
import gzip
import json
import re
import time

T0 = time.perf_counter()
import numpy as np  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.model_selection import KFold  # noqa: E402

ELEMENTS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
            "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb "
            "Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr").split()
TOK = re.compile(r"[A-Z][a-z]?|\d*\.\d+|\d+|[()\[\]]")
NUM = re.compile(r"\d*\.\d+|\d+")


def emit(step, **kw):
    print("METRIC " + json.dumps({"step": step, **kw, "wall_s": round(time.perf_counter() - T0, 3)}), flush=True)


def parse_formula(f):
    s = f.replace(" ", "")
    toks = TOK.findall(s)
    if "".join(toks) != s:
        raise ValueError(f"unparsed characters in {f!r}")
    stack, i = [{}], 0
    while i < len(toks):
        t = toks[i]
        i += 1
        if t in "([":
            stack.append({})
        elif t in ")]":
            grp, mult = stack.pop(), 1.0
            if i < len(toks) and NUM.fullmatch(toks[i]):
                mult, i = float(toks[i]), i + 1
            for el, n in grp.items():
                stack[-1][el] = stack[-1].get(el, 0.0) + n * mult
        elif t[0].isupper():
            if t not in ELEMENTS:
                raise ValueError(f"unknown element {t} in {f!r}")
            n = 1.0
            if i < len(toks) and NUM.fullmatch(toks[i]):
                n, i = float(toks[i]), i + 1
            stack[-1][t] = stack[-1].get(t, 0.0) + n
        else:
            raise ValueError(f"bad token {t} in {f!r}")
    if len(stack) != 1:
        raise ValueError(f"unbalanced brackets in {f!r}")
    return stack[0]


def cv_rf(X, y, trees, jobs, tag):
    kf = KFold(n_splits=5, shuffle=True, random_state=18012019)
    maes, dummy, fold_s = [], [], []
    for k, (tr, te) in enumerate(kf.split(X)):
        t = time.perf_counter()
        rf = RandomForestRegressor(n_estimators=trees, n_jobs=jobs, random_state=0)
        rf.fit(X[tr], y[tr])
        mae = float(np.abs(rf.predict(X[te]) - y[te]).mean())
        fold_s.append(time.perf_counter() - t)
        maes.append(mae)
        dummy.append(float(np.abs(y[tr].mean() - y[te]).mean()))
        emit("fold", feat=tag, fold=k, mae=round(mae, 4), dummy_mae=round(dummy[-1], 4), fold_s=round(fold_s[-1], 2))
    emit("cv_done", feat=tag, n=len(y), n_features=int(X.shape[1]), trees=trees, jobs=jobs,
         mae_mean=round(float(np.mean(maes)), 4), mae_std=round(float(np.std(maes)), 4),
         dummy_mae=round(float(np.mean(dummy)), 4), cv_total_s=round(sum(fold_s), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--magpie", action="store_true")
    ap.add_argument("--trees", type=int, default=500)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    t = time.perf_counter()
    d = json.load(gzip.open(a.file, "rt"))
    comps = [r[0] for r in d["data"]]
    y = np.array([float(r[1]) for r in d["data"]])
    emit("loaded", file=a.file, columns=d["columns"], n=len(y), target_mean=round(float(y.mean()), 4),
         target_frac_zero=round(float((y == 0).mean()), 4), load_s=round(time.perf_counter() - t, 3))
    t = time.perf_counter()
    parsed, bad = [], 0
    for c in comps:
        try:
            parsed.append(parse_formula(c))
        except ValueError:
            parsed.append({})
            bad += 1
    els = sorted({e for p in parsed for e in p}, key=ELEMENTS.index)
    X = np.zeros((len(parsed), len(els)))
    for r, p in enumerate(parsed):
        tot = sum(p.values()) or 1.0
        for e, n in p.items():
            X[r, els.index(e)] = n / tot
    emit("featurized", feat="frac", n_elements=len(els), parse_failures=bad, feat_s=round(time.perf_counter() - t, 3))
    cv_rf(X, y, a.trees, a.jobs, "frac")
    if a.magpie:
        t = time.perf_counter()
        from matminer.featurizers.composition import ElementProperty
        from pymatgen.core import Composition
        t_imp = time.perf_counter() - t
        ep = ElementProperty.from_preset("magpie")
        ep.set_n_jobs(1)
        t = time.perf_counter()
        Xm = np.array([ep.featurize(Composition(c)) for c in comps], dtype=float)
        nan_cols = int(np.isnan(Xm).any(0).sum())
        Xm = np.nan_to_num(Xm)
        emit("featurized", feat="magpie", n_features=int(Xm.shape[1]), nan_cols=nan_cols, import_s=round(t_imp, 2),
             feat_s=round(time.perf_counter() - t, 2))
        cv_rf(Xm, y, a.trees, a.jobs, "magpie")


if __name__ == "__main__":
    main()
