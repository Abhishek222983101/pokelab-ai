import os

import pytest

from pokelab_brain.papers.packs import get_pack


def test_grokking_pack_curated_claim():
    pack = get_pack("grokking")
    assert pack.hero is True
    assert pack.kit == "grokking"
    assert pack.claims[0].metric == "test accuracy"
    assert pack.claims[0].value == 0.95


def test_unknown_pack_raises():
    with pytest.raises(KeyError):
        get_pack("not-a-real-paper")


@pytest.mark.parametrize(
    ("paper_id", "kit"),
    [
        ("distillation", "distillation"),
        ("nerf", "nerf"),
        ("materials", "materials"),
        ("arena", "arena"),
    ],
)
def test_p11_pack_is_curated_not_hero(paper_id, kit):
    pack = get_pack(paper_id)
    assert pack.kit == kit
    assert pack.hero is False
    assert pack.claims and pack.claims[0].source_chunk_id == "curated"


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


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_claim_extraction_from_grokking_abstract(tmp_path):
    from pokelab_brain.llm.providers import GroqProvider
    from pokelab_brain.llm.router import LlmRouter
    from pokelab_brain.papers.claims import extract_claims
    from pokelab_brain.papers.ingest import PaperChunk

    chunk = PaperChunk(
        paper_id="grokking",
        chunk_id="grokking:abstract",
        section="Abstract",
        text=(
            "We train a 1-layer transformer to perform modular addition. "
            "After a long period of overfitting, with 100% training accuracy but "
            "near-chance test accuracy, the model suddenly transitions to 100% test "
            "accuracy, a phenomenon called grokking, at around step 10000."
        ),
    )
    router = LlmRouter(
        providers={"groq": GroqProvider(GROQ_KEY)},
        cache_db=tmp_path / "c.db",
        budget_db=tmp_path / "b.db",
    )
    try:
        claims = extract_claims(
            router, chunk, route=["groq"], model="openai/gpt-oss-20b", reasoning_effort="low"
        )
    finally:
        router.close()

    assert len(claims) >= 1, "expected the LLM to find at least the 100% test accuracy claim"
    assert any("accuracy" in c.metric.lower() for c in claims)
