import os

from pokelab_brain.papers.ingest import chunk_paper, ingest_pdf

GROKKING_PDF = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "papers", "2301.05217.pdf"
)


def test_chunk_paper_splits_on_headings():
    text = "Some preamble.\n\nAbstract\nThis is the abstract body.\n\nIntroduction\nThis is the intro body."
    chunks = chunk_paper("p1", text)
    sections = {c.section for c in chunks}
    assert "Abstract" in sections
    assert "Introduction" in sections


def test_chunk_paper_wraps_long_sections():
    text = "Results\n" + ("x" * 5000)
    chunks = chunk_paper("p1", text, max_chunk_chars=2000)
    assert len(chunks) == 3  # 5000 chars / 2000 -> 3 pieces
    assert all(c.section == "Results" for c in chunks)


def test_ingest_real_grokking_pdf():
    if not os.path.exists(GROKKING_PDF):
        import pytest
        pytest.skip("grokking PDF not present in data/papers/")
    chunks = ingest_pdf("grokking", GROKKING_PDF)
    assert len(chunks) > 5
    full_text = " ".join(c.text for c in chunks).lower()
    assert "grokking" in full_text
    assert "modular" in full_text or "generalization" in full_text
