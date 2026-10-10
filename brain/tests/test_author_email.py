import os

import pytest

from pokelab_brain.papers.packs import get_pack
from pokelab_brain.science.author_email import draft_email, save_draft
from pokelab_brain.science.comparator import compare


def _load_env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


def test_save_draft_writes_a_clearly_marked_file(tmp_path):
    path = save_draft(tmp_path, "proj1", "Dear Dr. Nanda, ...")
    content = path.read_text()
    assert "NOT sent automatically" in content
    assert "Dear Dr. Nanda" in content


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_email_draft(tmp_path):
    from pokelab_brain.llm.providers import GroqProvider
    from pokelab_brain.llm.router import LlmRouter

    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db", budget_db=tmp_path / "b.db",
    )
    pack = get_pack("grokking")
    comparison = compare({"test_acc": 0.9654}, "test_acc", pack)
    try:
        email = draft_email(
            router, route=["groq"], paper_title=pack.title, comparison=comparison,
            model="openai/gpt-oss-20b", reasoning_effort="low",
        )
    finally:
        router.close()

    assert len(email) > 20
    assert "subject" not in email.lower().split("\n")[0].lower()  # no subject line leaked in
