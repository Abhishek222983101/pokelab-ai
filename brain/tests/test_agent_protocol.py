import random
import string

import pytest

from pokelab_brain.agents.protocol import parse_response


def test_well_formed_action():
    text = '<thought>I should run the kit.</thought><action tool="run_kit">{"kit": "grokking", "config": {"steps": 100}}</action>'
    r = parse_response(text)
    assert r.thought == "I should run the kit."
    assert r.action.tool == "run_kit"
    assert r.action.args == {"kit": "grokking", "config": {"steps": 100}}
    assert r.final is None
    assert not r.malformed


def test_well_formed_final():
    text = '<thought>Done.</thought><final>{"summary": "grokked", "result": {"test_acc": 0.96}}</final>'
    r = parse_response(text)
    assert r.final == {"summary": "grokked", "result": {"test_acc": 0.96}}
    assert r.action is None
    assert not r.malformed


def test_action_with_prose_around_tags():
    text = 'Let me think.\n<thought>checking the paper</thought>\nOkay here is my action:\n<action tool="read_paper">{"paper_id": "grokking"}</action>\nI will wait for the result.'
    r = parse_response(text)
    assert r.thought == "checking the paper"
    assert r.action.tool == "read_paper"
    assert r.action.args == {"paper_id": "grokking"}


def test_final_with_non_json_body_is_salvaged():
    text = "<final>I'm done, the model grokked successfully.</final>"
    r = parse_response(text)
    assert r.final is not None
    assert "summary" in r.final
    assert r.malformed


def test_action_with_malformed_json_args_still_identifies_tool():
    text = '<action tool="run_kit">{kit: grokking, broken json</action>'
    r = parse_response(text)
    assert r.action.tool == "run_kit"
    assert r.action.args == {}
    assert r.malformed


def test_both_action_and_final_prefers_final():
    text = '<action tool="run_kit">{"kit":"x"}</action><final>{"summary": "done"}</final>'
    r = parse_response(text)
    assert r.final == {"summary": "done"}
    assert r.action is None
    assert r.malformed


def test_no_tags_at_all_salvages_whole_text_as_thought():
    text = "I think we should try the transformer model with frac 0.5."
    r = parse_response(text)
    assert r.thought == text
    assert r.action is None
    assert r.final is None
    assert r.malformed


def test_action_tool_with_single_quotes_not_matched_but_does_not_crash():
    # a model that uses single quotes for the attribute is out of spec;
    # we should not crash, even if we don't parse the action out
    text = "<action tool='run_kit'>{}</action>"
    r = parse_response(text)
    assert r.raw == text  # didn't crash; whole thing is salvageable as thought
    assert r.malformed


def test_unclosed_action_tag_does_not_crash():
    text = '<thought>hmm</thought><action tool="run_kit">{"kit": "grokking"}'
    r = parse_response(text)
    # unclosed tag: our regex requires a closing tag, so this degrades to
    # "thought found, no action" rather than crashing
    assert r.thought == "hmm"
    assert r.action is None


@pytest.mark.parametrize("seed", range(50))
def test_fuzz_random_garbage_never_raises(seed):
    rng = random.Random(seed)
    alphabet = string.printable
    garbage = "".join(rng.choice(alphabet) for _ in range(200))
    # must never raise, regardless of how broken the input is
    parse_response(garbage)


@pytest.mark.parametrize("seed", range(20))
def test_fuzz_near_valid_tags_never_raises(seed):
    rng = random.Random(seed)
    pieces = ["<thought>", "</thought>", "<action", 'tool="', '">', "</action>", "<final>", "</final>", "{", "}", '"', ":", rng.choice(string.ascii_letters)]
    text = "".join(rng.choice(pieces) for _ in range(30))
    parse_response(text)
