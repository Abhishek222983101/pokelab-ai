from pokelab_brain.agents.lifecycle import check_merge, check_refine, check_retire, check_spawn
from pokelab_labml.scout.coverage import find_gaps
from pokelab_labml.selector.thompson import AgentArm


def test_spawn_triggers_on_repeated_uncovered_capability():
    gaps = find_gaps(["analyze_3d", "analyze_3d", "analyze_3d"], agent_capabilities={})
    t = check_spawn(gaps)
    assert t.should_spawn
    assert t.capability == "analyze_3d"


def test_spawn_does_not_trigger_on_single_request():
    gaps = find_gaps(["rare_thing"], agent_capabilities={})
    t = check_spawn(gaps)
    assert not t.should_spawn


def test_refine_triggers_on_high_failure_rate():
    t = check_refine(n_tasks=6, failure_rate=0.5, format_error_rate=0.0)
    assert t.should_refine
    assert "failure rate" in t.reason


def test_refine_triggers_on_high_format_error_rate():
    t = check_refine(n_tasks=6, failure_rate=0.1, format_error_rate=0.25)
    assert t.should_refine


def test_refine_does_not_trigger_with_too_few_tasks():
    t = check_refine(n_tasks=2, failure_rate=0.9, format_error_rate=0.9)
    assert not t.should_refine


def test_merge_triggers_on_similar_underused_agents():
    t = check_merge(
        caps_a=["run_kit", "read_paper", "analyze"],
        caps_b=["run_kit", "read_paper"],
        assignment_frac_a=0.1, assignment_frac_b=0.15,
        spec_cosine=0.9,
    )
    assert t.should_merge


def test_merge_does_not_trigger_on_dissimilar_agents():
    t = check_merge(
        caps_a=["run_kit"], caps_b=["analyze_3d", "author_email", "discover"],
        assignment_frac_a=0.1, assignment_frac_b=0.1, spec_cosine=0.9,
    )
    assert not t.should_merge


def test_merge_does_not_trigger_when_heavily_assigned():
    t = check_merge(
        caps_a=["run_kit", "read_paper"], caps_b=["run_kit", "read_paper"],
        assignment_frac_a=0.5, assignment_frac_b=0.1, spec_cosine=0.9,
    )
    assert not t.should_merge


def test_retire_triggers_on_consistently_low_reward():
    # 10 near-failures, 0 successes -> Beta(1+0, 1+10)=Beta(1,11), very
    # confidently below 0.35
    arm = AgentArm(agent_id="bad", alpha=1.0, beta=11.0)
    t = check_retire(arm, n_tasks=10)
    assert t.should_retire
    assert "P(mean reward" in t.reason


def test_retire_does_not_trigger_on_good_performance():
    arm = AgentArm(agent_id="good", alpha=9.0, beta=2.0)
    t = check_retire(arm, n_tasks=10)
    assert not t.should_retire


def test_retire_does_not_trigger_with_too_few_tasks():
    arm = AgentArm(agent_id="new", alpha=1.0, beta=11.0)
    t = check_retire(arm, n_tasks=2)
    assert not t.should_retire


def test_retire_triggers_on_dominance():
    arm = AgentArm(agent_id="mediocre", alpha=3.0, beta=3.0)  # mean 0.5, not low-reward-triggered
    t = check_retire(arm, n_tasks=10, dominated_by=[("star", 0.97)])
    assert t.should_retire
    assert "dominated by star" in t.reason
