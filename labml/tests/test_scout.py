from pokelab_labml.scout.coverage import find_gaps, should_spawn


def test_no_gap_when_fully_covered():
    gaps = find_gaps(["run_kit", "read_paper"], {"eevee": ["run_kit", "read_paper"]})
    assert gaps == []


def test_finds_and_counts_gaps():
    requested = ["analyze_3d", "analyze_3d", "run_kit", "analyze_3d"]
    gaps = find_gaps(requested, {"eevee": ["run_kit"]})
    assert len(gaps) == 1
    assert gaps[0].capability == "analyze_3d"
    assert gaps[0].requested_count == 3


def test_should_spawn_filters_by_threshold():
    requested = ["x", "x", "y"]
    gaps = find_gaps(requested, {})
    spawn_list = should_spawn(gaps, min_requests_to_act=2)
    assert spawn_list == ["x"]
