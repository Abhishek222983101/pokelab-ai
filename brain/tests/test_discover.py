import time

from pokelab_brain.papers.discover import ArxivCache, search_arxiv


def test_real_arxiv_search_finds_the_grokking_paper(tmp_path):
    cache = ArxivCache(tmp_path / "arxiv_cache.db")
    try:
        results = search_arxiv("grokking generalization modular arithmetic transformer", k=5, cache=cache)
    finally:
        cache.close()

    assert len(results) > 0
    titles = " ".join(r.title.lower() for r in results)
    assert "grok" in titles or "generaliz" in titles


def test_cache_avoids_a_second_network_call(tmp_path):
    cache = ArxivCache(tmp_path / "arxiv_cache.db")
    try:
        t0 = time.perf_counter()
        results1 = search_arxiv("grokking neural networks", k=3, cache=cache)
        first_elapsed = time.perf_counter() - t0

        t0 = time.perf_counter()
        results2 = search_arxiv("grokking neural networks", k=3, cache=cache)
        second_elapsed = time.perf_counter() - t0
    finally:
        cache.close()

    assert [r.arxiv_id for r in results1] == [r.arxiv_id for r in results2]
    assert second_elapsed < first_elapsed / 2, "cached lookup should be much faster than a real API call"
