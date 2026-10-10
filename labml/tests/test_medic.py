from pokelab_labml.medic.classifier import diagnose


def test_recognizes_oom():
    d = diagnose("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB")
    assert d.error_class == "oom"


def test_recognizes_unknown_kit():
    d = diagnose("unknown_kit:'nope'")
    assert d.error_class == "unknown_kit"


def test_recognizes_nan():
    d = diagnose("loss became NaN at step 4210")
    assert d.error_class == "nan"


def test_no_error_returns_none_class():
    d = diagnose(None)
    assert d.error_class == "none"


def test_unrecognized_error_is_unknown():
    d = diagnose("some completely novel error we've never seen before xyz123")
    assert d.error_class == "unknown"
    assert "human" in d.suggested_fix
