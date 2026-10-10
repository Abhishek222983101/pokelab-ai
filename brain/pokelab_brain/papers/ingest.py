"""Paper ingestion: PDF -> plain text -> chunks (§10.4 `paper_chunks`
table: `paper_id, chunk_id, section, text`). Section detection is
heuristic (a line that looks like a heading), which is honest about what
this is — a real PDF has no structured markup, so "section" here is a
best-effort label, not ground truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# Headings in ML papers are short, usually title-cased or ALL CAPS, and
# never end in a period (prose does).
_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?([A-Z][A-Za-z0-9 ,\-:]{2,60})\s*$"
)
_COMMON_HEADINGS = {
    "abstract", "introduction", "related work", "background", "method",
    "methods", "experiments", "results", "discussion", "conclusion",
    "conclusions", "references", "acknowledgements", "appendix",
}


@dataclass
class PaperChunk:
    paper_id: str
    chunk_id: str
    section: str
    text: str


def extract_text(pdf_path: str | Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_paper(paper_id: str, text: str, max_chunk_chars: int = 2000) -> list[PaperChunk]:
    """Splits on detected headings first, then hard-wraps any section that's
    still too long for one LLM call's worth of context."""
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = [("preamble", [])]

    for line in lines:
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m and (stripped.lower() in _COMMON_HEADINGS or m.group(1).lower() in _COMMON_HEADINGS):
            sections.append((stripped, []))
        else:
            sections[-1][1].append(line)

    chunks: list[PaperChunk] = []
    chunk_idx = 0
    for section_name, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        for start in range(0, len(body), max_chunk_chars):
            piece = body[start : start + max_chunk_chars]
            chunks.append(PaperChunk(paper_id=paper_id, chunk_id=f"{paper_id}:{chunk_idx}", section=section_name, text=piece))
            chunk_idx += 1

    return chunks


def ingest_pdf(paper_id: str, pdf_path: str | Path) -> list[PaperChunk]:
    text = extract_text(pdf_path)
    return chunk_paper(paper_id, text)
