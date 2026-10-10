import json
import os

from pokelab_labml.cli import train_all

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "grok_sweep.json")


def test_train_all_reports_every_model():
    report = train_all(FIXTURE)
    assert set(report["models"]) == {"oracle", "navigator", "medic", "scout", "selector"}
    assert report["models"]["oracle"]["status"] == "trained"
    assert report["models"]["navigator"]["status"] == "trained"
