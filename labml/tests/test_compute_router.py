from pokelab_labml.router.placement import choose_placement


def test_uses_local_when_a_slot_is_free_and_fits():
    d = choose_placement(estimated_wall_s=20, local_free_slots=1, local_vram_headroom_mib=2000, required_vram_mib=500)
    assert d.target == "local"


def test_falls_back_to_kaggle_for_long_jobs_when_local_full():
    d = choose_placement(estimated_wall_s=600, local_free_slots=0, local_vram_headroom_mib=0, required_vram_mib=500)
    assert d.target == "kaggle"


def test_falls_back_to_colab_for_short_jobs_when_local_full():
    d = choose_placement(estimated_wall_s=20, local_free_slots=0, local_vram_headroom_mib=0, required_vram_mib=500)
    assert d.target == "colab"


def test_queues_locally_when_no_remote_available():
    d = choose_placement(estimated_wall_s=600, local_free_slots=0, local_vram_headroom_mib=0,
                          required_vram_mib=500, remote_available=False)
    assert d.target == "local"


def test_insufficient_vram_even_with_free_slot_goes_remote():
    d = choose_placement(estimated_wall_s=20, local_free_slots=1, local_vram_headroom_mib=100, required_vram_mib=500)
    assert d.target in ("kaggle", "colab")
