from pokelab_brain.llm.jsonio import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_in_prose():
    text = 'Sure! Here is the result: {"a": 1, "b": [1, 2]} Hope that helps!'
    assert extract_json(text) == {"a": 1, "b": [1, 2]}


def test_fenced_json():
    text = "Here you go:\n```json\n{\n  \"a\": 1\n}\n```\nDone."
    assert extract_json(text) == {"a": 1}


def test_trailing_comma_repaired():
    text = '{"a": 1, "b": 2,}'
    assert extract_json(text) == {"a": 1, "b": 2}


def test_list_in_prose():
    text = 'The plan is [1, 2, 3] as discussed.'
    assert extract_json(text) == [1, 2, 3]


def test_no_json_returns_none():
    assert extract_json("no json here at all") is None


def test_nested_object_with_prose_wrapper():
    text = 'Result:\n{"agent": {"name": "eevee", "tags": ["x", "y",]}, "ok": true}\nthanks'
    assert extract_json(text) == {"agent": {"name": "eevee", "tags": ["x", "y"]}, "ok": True}
