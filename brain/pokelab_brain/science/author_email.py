"""`author_email` (§6.11, Scribe capability): drafts a polite email to a
paper's corresponding author summarizing the reproduction and any open
discrepancy. Saved as a draft file — §6.11 is explicit this is **never
sent automatically**, so this module has no send path at all, not even
a disabled one.
"""
from __future__ import annotations

from pathlib import Path

from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.science.comparator import ComparisonReport

_DRAFT_PROMPT = """Draft a short, polite, professional email to the corresponding author of
this paper, summarizing an independent reproduction attempt.

Paper: {paper_title}
Author name (if known, else write "Dr. [Author]"): {author_name}

Our result: {narrative}

Write ONLY the email body (no subject line, no signature block beyond
"Best regards,"). Keep it under 200 words, factual, and generous — this
is a hobby/educational reproduction, not a critique.
"""


def draft_email(
    router: LlmRouter,
    route: list[str],
    paper_title: str,
    comparison: ComparisonReport,
    author_name: str = "",
    **llm_kwargs,
) -> str:
    prompt = _DRAFT_PROMPT.format(
        paper_title=paper_title,
        author_name=author_name or "Dr. [Author]",
        narrative=comparison.narrative,
    )
    result = router.complete(messages=[{"role": "user", "content": prompt}], route=route, max_tokens=400, **llm_kwargs)
    return result.content.strip()


def save_draft(var_dir: str | Path, project: str, email_body: str) -> Path:
    """Saved under var/notes/<project>/ alongside the other notes — never
    anywhere near a mail-send path."""
    path = Path(var_dir) / "notes" / project / "author_email_draft.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Draft email — NOT sent automatically, review before sending\n\n{email_body}\n")
    return path
