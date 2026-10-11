"""`just contracts`: regenerates schemas/*.json from the pydantic models
here, and copies TS types to web/app/lib/contracts/ (hand-written for
now — see the module docstring in ts/index.d.ts for why)."""
from __future__ import annotations

import json
from pathlib import Path

from pokelab_contracts.agents import AgentSpec
from pokelab_contracts.envelope import Event, NewEvent
from pokelab_contracts.jobs import DoneLine, MetricLine
from pokelab_contracts.papers import PaperPack

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

MODELS = {
    "event": Event,
    "new_event": NewEvent,
    "agent_spec": AgentSpec,
    "metric_line": MetricLine,
    "done_line": DoneLine,
    "paper_pack": PaperPack,
}


def export_schemas() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        (SCHEMAS_DIR / f"{name}.json").write_text(json.dumps(schema, indent=2))


if __name__ == "__main__":
    export_schemas()
    print(f"wrote {len(MODELS)} schemas to {SCHEMAS_DIR}")
