"""Known event `kind` strings this system actually publishes, grouped —
kept as a single source so a new event kind gets added here first, and
the three implementations (Rust store, Python brain, TS LabEvent
handling) are checked against it in fixtures.py's golden examples.
"""
JOB_EVENT_KINDS = {"job.started", "job.metric", "job.log", "job.done"}
LIFECYCLE_EVENT_KINDS = {
    "agent.spawned", "agent.retired", "agent.evolved", "agent.merged",
    "agent.refine_recommended", "agent.merge_recommended",
}
# Oak's runtime (brain/pokelab_brain/oak/runtime.py + scheduler emit) — the §2.7 binding-table causes
TASK_EVENT_KINDS = {"agent.task_started", "agent.task_finished", "agent.task_failed", "agent.rewarded"}
PROJECT_EVENT_KINDS = {"project.requested", "project.created", "project.rejected", "project.completed", "project.badge_awarded"}
HUMAN_EVENT_KINDS = {"human.feedback"}
ALL_KNOWN_KINDS = JOB_EVENT_KINDS | LIFECYCLE_EVENT_KINDS | TASK_EVENT_KINDS | PROJECT_EVENT_KINDS | HUMAN_EVENT_KINDS
