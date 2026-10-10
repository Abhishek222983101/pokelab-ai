import pytest

from pokelab_brain.memory.pokedex import Pokedex


def test_save_lesson_requires_evidence(tmp_path):
    pdx = Pokedex(tmp_path / "brain.db")
    with pytest.raises(ValueError, match="cite the run"):
        pdx.save_lesson("wd=0 never grokked", kind="training", evidence=[])


def test_save_and_search_lesson(tmp_path):
    pdx = Pokedex(tmp_path / "brain.db")
    pdx.save_lesson(
        "wd=0 never grokked in 30k steps at frac 0.3 — see job_abc123",
        kind="training", evidence=["job_abc123"],
    )
    pdx.save_lesson(
        "frac=0.5 groks much faster than frac=0.3 for modular addition",
        kind="training", evidence=["job_def456"],
    )
    pdx.save_lesson(
        "distillation at T=4 beats hard-label training on MNIST",
        kind="distillation", evidence=["job_ghi789"],
    )

    results = pdx.search_lessons("grok frac modular")
    assert len(results) >= 1
    assert any("frac" in r.text for r in results)
    # the distillation lesson shouldn't outrank the more relevant ones
    assert results[0].kind == "training"


def test_search_lessons_filters_by_kind(tmp_path):
    pdx = Pokedex(tmp_path / "brain.db")
    pdx.save_lesson("a training lesson about grokking", kind="training", evidence=["j1"])
    pdx.save_lesson("a distillation lesson about grokking", kind="distillation", evidence=["j2"])
    results = pdx.search_lessons("grokking", kind="distillation")
    assert len(results) == 1
    assert results[0].kind == "distillation"


def test_fix_library_exact_lookup_and_counting(tmp_path):
    pdx = Pokedex(tmp_path / "brain.db")
    assert pdx.lookup_fix("oom:transformer") is None

    pdx.record_fix("oom:transformer", "oom", "halve batch size", succeeded=True, source_job="job1")
    fix = pdx.lookup_fix("oom:transformer")
    assert fix.success == 1 and fix.failure == 0

    pdx.record_fix("oom:transformer", "oom", "halve batch size", succeeded=True, source_job="job2")
    fix = pdx.lookup_fix("oom:transformer")
    assert fix.success == 2

    pdx.record_fix("oom:transformer", "oom", "halve batch size", succeeded=False, source_job="job3")
    fix = pdx.lookup_fix("oom:transformer")
    assert fix.success == 2 and fix.failure == 1


def test_persists_across_reopen(tmp_path):
    db_path = tmp_path / "brain.db"
    pdx1 = Pokedex(db_path)
    pdx1.save_lesson("durable lesson", kind="x", evidence=["j1"])
    pdx1.close()

    pdx2 = Pokedex(db_path)
    results = pdx2.search_lessons("durable")
    assert len(results) == 1
