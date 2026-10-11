"""Known event `kind` strings this system actually publishes, grouped —
kept as a single source so a new event kind gets added here first, and
the three implementations (Rust store, Python brain, TS LabEvent
handling) are checked against it in fixtures.py's golden examples.
"""
JOB_EVENT_KINDS = {"job.metric", "job.log", "job.done"}
LIFECYCLE_EVENT_KINDS = {
    "agent.spawned", "agent.retired", "agent.evolved", "agent.merged",
    "agent.refine_recommended", "agent.merge_recommended",
}
ALL_KNOWN_KINDS = JOB_EVENT_KINDS | LIFECYCLE_EVENT_KINDS
