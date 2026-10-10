from pokelab_brain.science.notes import append_note, list_notes, read_note, write_note


def test_write_and_read_note(tmp_path):
    write_note(tmp_path, "proj1", "results.md", "# Results\n\ngrokked at step 2800.")
    content = read_note(tmp_path, "proj1", "results.md")
    assert "grokked" in content


def test_append_note_accumulates_with_timestamp(tmp_path):
    write_note(tmp_path, "proj1", "plan.md", "v1 plan")
    append_note(tmp_path, "proj1", "plan.md", "v2 revision: switched to frac=0.5")
    content = read_note(tmp_path, "proj1", "plan.md")
    assert "v1 plan" in content
    assert "v2 revision" in content
    assert "---" in content  # revision separator


def test_read_missing_note_returns_none(tmp_path):
    assert read_note(tmp_path, "proj1", "nope.md") is None


def test_list_notes(tmp_path):
    write_note(tmp_path, "proj1", "plan.md", "x")
    write_note(tmp_path, "proj1", "results.md", "y")
    assert list_notes(tmp_path, "proj1") == ["plan.md", "results.md"]
