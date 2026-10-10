from pokelab_workers.remote.dispatch import dispatch


def test_dispatch_prefers_local_when_a_slot_is_free():
    result = dispatch(
        estimated_wall_s=20, local_free_slots=1, local_vram_headroom_mib=2000,
        required_vram_mib=500, script_path="unused.py",
    )
    assert result.target == "local"
    assert result.protocol_lines == []


def test_dispatch_to_colab_for_a_short_job_with_no_local_slot():
    # we don't actually want this test to rent a real Colab VM every run —
    # it exercises the ROUTING decision; the real colab path is covered
    # by test_colab_runner.py's live round trip
    import pokelab_workers.remote.dispatch as dispatch_module

    called = {}

    def fake_run_on_colab(script_path, gpu, timeout_s):
        called["args"] = (script_path, gpu, timeout_s)
        from pokelab_workers.remote.colab_runner import RemoteRunResult
        return RemoteRunResult(returncode=0, stdout="", stderr="", protocol_lines=[{"t": "done", "status": "ok"}])

    original = dispatch_module.run_on_colab
    dispatch_module.run_on_colab = fake_run_on_colab
    try:
        result = dispatch(
            estimated_wall_s=20, local_free_slots=0, local_vram_headroom_mib=0,
            required_vram_mib=500, script_path="smoke.py",
        )
    finally:
        dispatch_module.run_on_colab = original

    assert result.target == "colab"
    assert called["args"][0] == "smoke.py"
    assert result.protocol_lines[0]["status"] == "ok"


def test_dispatch_to_kaggle_requires_kernel_info():
    import pytest

    with pytest.raises(ValueError, match="kaggle dispatch needs"):
        dispatch(
            estimated_wall_s=600, local_free_slots=0, local_vram_headroom_mib=0,
            required_vram_mib=500, script_path="smoke.py",
        )
