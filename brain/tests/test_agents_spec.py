import os

from pokelab_brain.agents.spec import load_prompt, load_roster

ROSTER_TOML = os.path.join(os.path.dirname(__file__), "..", "..", "config", "roster.toml")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "pokelab_brain", "agents", "prompts")


def test_load_real_roster():
    specs = load_roster(ROSTER_TOML)
    assert len(specs) == 2
    species = {s.species for s in specs}
    assert species == {"eevee", "oak"}
    eevee = next(s for s in specs if s.species == "eevee")
    assert "run_kit" in eevee.capabilities


def test_load_prompt_for_each_roster_entry():
    specs = load_roster(ROSTER_TOML)
    for spec in specs:
        text = load_prompt(PROMPTS_DIR, spec.prompt_ref)
        assert "__TOOL_LIST__" in text
        assert "__TASK__" in text
