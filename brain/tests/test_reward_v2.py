from pokelab_brain.reward_v2 import compute_reward_v2, quality_implement, quality_run_experiment


def test_perfect_fast_cheap_success_scores_near_one():
    r = compute_reward_v2(
        success=True, quality=1.0, latency_s=1.0, latency_budget_s=10.0,
        tokens_used=100, token_budget=1000, gpu_s=1.0, gpu_budget_s=100.0,
    )
    assert r.reward > 0.9


def test_fast_cheap_failure_scores_low():
    r = compute_reward_v2(
        success=False, quality=0.0, latency_s=1.0, latency_budget_s=10.0,
        tokens_used=100, token_budget=1000, gpu_s=1.0, gpu_budget_s=100.0,
    )
    # §6.9: "a fast failure scores <= 0.2" — still retirable
    assert r.reward <= 0.2


def test_human_feedback_pulls_reward_toward_it():
    kwargs = dict(
        success=True, quality=0.9, latency_s=1.0, latency_budget_s=10.0,
        tokens_used=100, token_budget=1000, gpu_s=1.0, gpu_budget_s=100.0,
    )
    r_no_feedback = compute_reward_v2(**kwargs)
    r_thumbs_down = compute_reward_v2(**kwargs, human_feedback=0.0)
    assert r_thumbs_down.reward < r_no_feedback.reward


def test_over_budget_cost_term_hurts_reward():
    cheap = compute_reward_v2(
        success=True, quality=0.8, latency_s=1.0, latency_budget_s=10.0,
        tokens_used=10, token_budget=1000, gpu_s=1.0, gpu_budget_s=100.0,
    )
    expensive = compute_reward_v2(
        success=True, quality=0.8, latency_s=1.0, latency_budget_s=10.0,
        tokens_used=5000, token_budget=1000, gpu_s=500.0, gpu_budget_s=100.0,
    )
    assert expensive.reward < cheap.reward


def test_quality_run_experiment_matches_target_exactly():
    assert quality_run_experiment(0.95, 0.95, tolerance=0.05) == 1.0


def test_quality_run_experiment_partial_credit():
    q = quality_run_experiment(0.90, 0.95, tolerance=0.05)
    assert 0.0 <= q < 1.0


def test_quality_implement_levels():
    assert quality_implement("ok", metric_present=True) == 1.0
    assert quality_implement("ok", metric_present=False) == 0.5
    assert quality_implement("error", metric_present=False) == 0.0
