"""The brain-side doctor (P12.1): structural checks don't need network,
the real reachability checks skip cleanly without keys (matching the
rest of this repo's "skip, don't fake" convention for live providers).
"""
import os

from pokelab_brain.doctor import check_kaggle_auth, check_wandb_mode, main, run


def test_run_returns_all_six_checks():
    results = run()
    names = {r.name for r in results}
    assert names == {"elevate_gateway", "groq", "kaggle_auth", "kaggle_cli", "colab_auth", "wandb_mode"}
    for r in results:
        assert r.status in {"ok", "warn", "fail"}


def test_kaggle_auth_check_is_honest_when_absent(monkeypatch):
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    result = check_kaggle_auth()
    assert result.status == "warn"
    assert "unavailable" in result.detail


def test_wandb_mode_offline_by_default(monkeypatch):
    monkeypatch.delenv("WANDB_MODE", raising=False)
    result = check_wandb_mode()
    assert result.status == "ok"
    assert "offline" in result.detail


def test_main_exit_code_is_zero_when_nothing_fails(capsys):
    code = main()
    out = capsys.readouterr().out
    assert code == 0  # warn (missing optional creds) never fails the whole doctor
    assert "elevate_gateway" in out
