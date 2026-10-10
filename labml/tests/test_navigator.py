import json
import os

from pokelab_labml.navigator.gp import Navigator

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "grok_sweep.json")


def test_navigator_fits_real_sweep_and_predicts_plausible_shape():
    with open(FIXTURE) as f:
        sweep = json.load(f)

    # the REAL (frac, final_test_acc) pairs from the P5.1 sweep
    fracs = {"j_0.3": 0.3, "j_0.4": 0.4, "j_0.5": 0.5, "j_0.6": 0.6}
    x = [fracs[jid] for jid in sweep]
    y = [job["final"]["test_acc"] for job in sweep.values()]

    nav = Navigator()
    nav.fit(x, y)

    # interpolating near a point we actually ran should be closeish to it
    mean_at_05, _ = nav.predict(0.5)
    assert mean_at_05 > 0.7, f"GP should predict a high test_acc near frac=0.5 (got {mean_at_05})"

    mean_at_03, _ = nav.predict(0.3)
    assert mean_at_03 < mean_at_05, "GP should reflect that frac=0.3 performed worse than 0.5 in the real data"


def test_navigator_suggests_a_candidate():
    with open(FIXTURE) as f:
        sweep = json.load(f)
    fracs = {"j_0.3": 0.3, "j_0.4": 0.4, "j_0.5": 0.5, "j_0.6": 0.6}
    x = [fracs[jid] for jid in sweep]
    y = [job["final"]["test_acc"] for job in sweep.values()]

    nav = Navigator()
    nav.fit(x, y)
    candidates = [0.25, 0.35, 0.45, 0.55, 0.65, 0.7]
    suggestion = nav.suggest_next(candidates)
    assert suggestion.x in candidates
    assert 0.0 <= suggestion.predicted_mean <= 1.5  # GP mean can slightly overshoot [0,1], that's expected/untrimmed
