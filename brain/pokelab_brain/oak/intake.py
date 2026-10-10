"""Oak's intake (§6.2.1): turns a research request into a ProjectSpec.
The demo papers are template-matched by rule (no LLM needed to recognize
"reproduce the grokking paper"); only free-text questions go through a
real LLM call.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pokelab_brain.llm.jsonio import extract_json
from pokelab_brain.llm.router import LlmRouter

KNOWN_PAPERS = {"grokking", "distillation", "nerf", "matbench", "arena"}


class ProjectSpec(BaseModel):
    title: str
    kind: Literal["reproduce", "whatif", "compare", "explore", "discover"]
    goal: str
    papers: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    autonomy: Literal["ask_all", "default", "autopilot"] = "default"


_INTAKE_PROMPT = """Classify this research request into fields for a ProjectSpec.

Request: {text}

Reply with ONLY a JSON object (no prose, no code fence) shaped exactly like:
{{"title": "...", "kind": "reproduce|whatif|compare|explore|discover", "goal": "one sentence",
  "papers": [], "questions": [], "datasets": [], "repos": [], "constraints": {{}}}}
"""


def intake(text: str, router: LlmRouter | None = None, route: list[str] | None = None, **llm_kwargs) -> ProjectSpec:
    lowered = text.lower()
    matched_paper = next((p for p in KNOWN_PAPERS if p in lowered), None)

    if matched_paper and router is None:
        # template-matched, no LLM needed at all
        return ProjectSpec(title=f"Reproduce {matched_paper}", kind="reproduce", goal=text, papers=[matched_paper])

    if router is None or route is None:
        raise ValueError("intake needs a router+route for free-text requests that don't match a known paper")

    result = router.complete(messages=[{"role": "user", "content": _INTAKE_PROMPT.format(text=text)}], route=route, max_tokens=400, **llm_kwargs)
    parsed = extract_json(result.content)
    if not isinstance(parsed, dict):
        raise ValueError(f"intake did not return valid JSON: {result.content!r}")

    if matched_paper:
        parsed.setdefault("papers", [])
        if matched_paper not in parsed["papers"]:
            parsed["papers"].append(matched_paper)
        parsed["kind"] = "reproduce"

    return ProjectSpec(**parsed)
