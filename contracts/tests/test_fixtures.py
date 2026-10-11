import json
import os

from pokelab_contracts.agents import AgentSpawnedPayload
from pokelab_contracts.envelope import Event
from pokelab_contracts.events import ALL_KNOWN_KINDS

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


def test_job_started_fixture_validates_as_event():
    data = _load("job_started_event.json")
    event = Event(**data)
    assert event.kind in ALL_KNOWN_KINDS
    assert event.payload["kit"] == "grokking"


def test_job_metric_fixture_validates_as_event():
    data = _load("job_metric_event.json")
    event = Event(**data)
    assert event.kind in ALL_KNOWN_KINDS
    assert event.payload["job_id"] == "job-1"


def test_job_done_fixture_validates_as_event():
    data = _load("job_done_event.json")
    event = Event(**data)
    assert event.kind in ALL_KNOWN_KINDS
    assert event.payload["status"] == "ok"


def test_agent_spawned_fixture_validates_as_event_and_typed_payload():
    data = _load("agent_spawned_event.json")
    event = Event(**data)
    assert event.kind in ALL_KNOWN_KINDS
    payload = AgentSpawnedPayload(**event.payload)
    assert payload.capability == "analyze_3d"


def test_every_fixture_file_is_covered_by_a_test():
    """If a fixture gets added without a corresponding validation, this
    test fails loudly instead of the fixture silently rotting."""
    tested = {"job_started_event.json", "job_metric_event.json", "job_done_event.json", "agent_spawned_event.json"}
    on_disk = {f for f in os.listdir(FIXTURES_DIR) if f.endswith(".json")}
    assert on_disk == tested, f"untested fixtures: {on_disk - tested}"
