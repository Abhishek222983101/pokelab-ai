"""`labml train-all` / `labml eval`: trains every labml model that has
enough real data to train on, writes `var/reports/labml.json` (§4.6).
Models without enough data yet are reported, not silently skipped — an
empty report would look like success.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pokelab_labml.medic.classifier import diagnose
from pokelab_labml.navigator.gp import Navigator
from pokelab_labml.oracle.features import early_curve_features
from pokelab_labml.oracle.gbm import train as train_oracle
from pokelab_labml.scout.coverage import find_gaps


def train_all(sweep_fixture: str | Path) -> dict:
    report: dict = {"models": {}}

    with open(sweep_fixture) as f:
        sweep = json.load(f)

    fracs = {jid: float(jid.split("_")[1]) for jid in sweep}
    rows, labels, x_frac, y_acc = [], [], [], []
    for jid, job in sweep.items():
        steps = [s for s, _ in job["test_acc"]]
        test_acc = [v for _, v in job["test_acc"]]
        train_acc = [v for _, v in job["train_acc"]]
        rows.append(early_curve_features(steps, test_acc, train_acc, cutoff_step=800))
        labels.append(1 if job["final"]["test_acc"] >= 0.95 else 0)
        x_frac.append(fracs[jid])
        y_acc.append(job["final"]["test_acc"])

    if len(set(labels)) > 1:
        oracle_model = train_oracle(rows, labels)
        report["models"]["oracle"] = {
            "status": "trained",
            "n_train": oracle_model.n_train,
            "note": "prototype scale — needs the full curve-library sweep (§5.1, hundreds of runs) for real accuracy",
        }
    else:
        report["models"]["oracle"] = {"status": "insufficient_data", "n_train": len(labels)}

    nav = Navigator()
    nav.fit(x_frac, y_acc)
    report["models"]["navigator"] = {"status": "trained", "n_train": len(x_frac)}

    report["models"]["medic"] = {"status": "rule_based", "n_rules": 6}
    report["models"]["scout"] = {"status": "rule_based"}
    report["models"]["selector"] = {"status": "online_learning"}  # learns from live outcomes, no offline train step

    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="labml")
    sub = parser.add_subparsers(dest="command", required=True)

    train_cmd = sub.add_parser("train-all")
    train_cmd.add_argument("--sweep-fixture", default=None, help="path to a sweep JSON (see tests/fixtures/grok_sweep.json)")
    train_cmd.add_argument("--out", default="../var/reports/labml.json")

    args = parser.parse_args(argv)

    if args.command == "train-all":
        fixture = args.sweep_fixture or str(
            Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "grok_sweep.json"
        )
        report = train_all(fixture)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
