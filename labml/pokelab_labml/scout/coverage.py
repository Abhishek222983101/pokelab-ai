"""Scout (§7.6): does the roster actually cover what's being asked of it?
A coverage gap (a requested capability no active agent has) is the
trigger for Oak to spawn a new specialist (P6.2) — Scout's whole job is
turning "agent X failed because it doesn't know Y" into a crisp signal,
not prose.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoverageGap:
    capability: str
    requested_count: int


def find_gaps(
    requested_capabilities: list[str],
    agent_capabilities: dict[str, list[str]],
) -> list[CoverageGap]:
    """`agent_capabilities` maps agent_id -> capabilities for ACTIVE agents
    only (retired/shadow agents don't count toward coverage)."""
    covered: set[str] = set()
    for caps in agent_capabilities.values():
        covered.update(caps)

    counts: dict[str, int] = {}
    for cap in requested_capabilities:
        if cap not in covered:
            counts[cap] = counts.get(cap, 0) + 1

    return [CoverageGap(capability=c, requested_count=n) for c, n in sorted(counts.items(), key=lambda kv: -kv[1])]


def should_spawn(gaps: list[CoverageGap], min_requests_to_act: int = 2) -> list[str]:
    """Only act on a gap that's been hit more than once — a single odd
    request shouldn't spawn a whole new agent (§6.2's spawn is not free:
    it costs an LLM call and roster complexity)."""
    return [g.capability for g in gaps if g.requested_count >= min_requests_to_act]
