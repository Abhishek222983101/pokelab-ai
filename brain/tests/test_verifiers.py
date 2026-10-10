from pokelab_brain.agents.verifiers import run_all_checks, run_check


def test_file_exists_check(tmp_path):
    f = tmp_path / "chunks.json"
    f.write_text("{}")
    result = run_check("file_exists:chunks", {"artifacts": {"chunks": str(f)}})
    assert result.passed

    result2 = run_check("file_exists:missing", {"artifacts": {}})
    assert not result2.passed


def test_json_schema_valid_check():
    assert run_check("json_schema_valid:pack", {"artifacts": {"pack": {"a": 1}}}).passed
    assert not run_check("json_schema_valid:pack", {"artifacts": {"pack": "not a dict"}}).passed


def test_config_validates_check():
    assert run_check("config_validates:grokking", {}).passed
    assert not run_check("config_validates:not_a_kit", {}).passed


def test_job_completed_check():
    ctx = {"jobs": {"smoke": {"status": "ok"}}}
    assert run_check("job_completed:smoke", ctx).passed
    ctx2 = {"jobs": {"smoke": {"status": "error"}}}
    assert not run_check("job_completed:smoke", ctx2).passed


def test_metric_present_check():
    assert run_check("metric_present:test_acc", {"final": {"test_acc": 0.96}}).passed
    assert not run_check("metric_present:test_acc", {"final": {}}).passed


def test_metric_threshold_check_real_grokking_number():
    ctx = {"final": {"test_acc": 0.9654}}
    assert run_check("metric_threshold:test_acc,>=,0.95", ctx).passed
    assert not run_check("metric_threshold:test_acc,>=,0.99", ctx).passed


def test_report_has_sections_check():
    ctx = {"report_text": "## Summary\nok\n## Evidence\nnumbers\n## Narrative\ntext"}
    assert run_check("report_has_sections:summary,evidence,narrative", ctx).passed
    assert not run_check("report_has_sections:summary,conclusion", ctx).passed


def test_numbers_match_evidence_check():
    assert run_check("numbers_match_evidence", {"narrative_is_template_fallback": False}).passed
    assert not run_check("numbers_match_evidence", {"narrative_is_template_fallback": True}).passed


def test_unknown_check_fails_safe():
    result = run_check("not_a_real_check:x", {})
    assert not result.passed


def test_run_all_checks_requires_every_one_to_pass():
    ctx = {"final": {"test_acc": 0.96}, "jobs": {"full": {"status": "ok"}}}
    ok, results = run_all_checks(["job_completed:full", "metric_threshold:test_acc,>=,0.9"], ctx)
    assert ok
    assert len(results) == 2

    ok2, _ = run_all_checks(["job_completed:full", "metric_threshold:test_acc,>=,0.99"], ctx)
    assert not ok2
