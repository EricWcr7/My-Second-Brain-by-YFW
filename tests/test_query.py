from llmwiki.query import _build_context, _format_directive, answer
from llmwiki.search import search
from llmwiki.store import read_page, write_page
from llmwiki.wiki import concept_path

from tests.fakes import FakeProvider


def _seed_pages(vault):
    # Three concept pages that all match the query "retrieval", so BM25 retrieves
    # every one as a rerank candidate.
    for title in ("Alpha", "Beta", "Gamma"):
        write_page(
            concept_path(vault, "projects/learning", title),
            {"title": title, "type": "concept", "section": "projects/learning", "sources": ["s1"]},
            f"Retrieval notes appear in {title}.",
        )


def _retrieval_order(vault):
    return [h.ref.slug for h in search(vault, "retrieval", section="projects/learning", top_k=8)]


def test_rerank_reorders_context_when_enabled(vault):
    vault.rerank = True
    _seed_pages(vault)
    provider = FakeProvider(rerank_order=["gamma", "alpha", "beta"])
    _blocks, used = _build_context(vault, provider, "retrieval", "projects/learning", 8)
    assert used == ["gamma", "alpha", "beta"]
    assert "parse:RerankResult" in provider.calls


def test_rerank_off_keeps_retrieval_order(vault):
    _seed_pages(vault)  # vault.rerank defaults to False
    provider = FakeProvider(rerank_order=["gamma", "alpha", "beta"])
    _blocks, used = _build_context(vault, provider, "retrieval", "projects/learning", 8)
    assert used == _retrieval_order(vault)
    assert "parse:RerankResult" not in provider.calls  # reranker never invoked


def test_rerank_failure_degrades_to_retrieval_order(vault):
    vault.rerank = True
    _seed_pages(vault)

    class _RerankBoom(FakeProvider):
        def parse(self, system, user, schema, *, model=None, max_tokens=16000):
            from llmwiki.rerank import RerankResult

            if schema is RerankResult:
                raise RuntimeError("rerank boom")
            return super().parse(system, user, schema, model=model, max_tokens=max_tokens)

    _blocks, used = _build_context(vault, _RerankBoom(), "retrieval", "projects/learning", 8)
    assert used == _retrieval_order(vault)  # a rerank failure never breaks Ask


def test_rerank_never_invents_or_drops_candidates(vault):
    vault.rerank = True
    _seed_pages(vault)
    # The model echoes one valid slug, one invented slug, and omits the other two.
    provider = FakeProvider(rerank_order=["gamma", "made-up-slug"])
    _blocks, used = _build_context(vault, provider, "retrieval", "projects/learning", 8)
    assert set(used) == {"alpha", "beta", "gamma"}  # invented dropped, none lost
    assert used[0] == "gamma"  # the one valid ranking is honored
    # Omitted candidates are appended in their original retrieval order.
    assert used[1:] == [s for s in _retrieval_order(vault) if s != "gamma"]


def test_answer_uses_retrieved_pages(vault):
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["s1"]},
        "Retrieval practice strengthens long-term recall.",
    )
    provider = FakeProvider(
        answer_text="Retrieval practice strengthens recall. [[retrieval-practice]]"
    )
    result = answer(vault, provider, "how does retrieval practice work", section="projects/learning")

    assert "retrieval" in result.answer.lower()
    assert "retrieval-practice" in result.pages_used
    assert "complete" in provider.calls


def test_answer_flags_invented_citation(vault):
    # The model cites a real page and invents one ([[made-up-page]]).
    # The grounding check must surface the invented one and keep it out of pages_used.
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["s1"]},
        "Retrieval practice strengthens long-term recall.",
    )
    provider = FakeProvider(answer_text="See [[retrieval-practice]] and also [[made-up-page]].")
    result = answer(vault, provider, "how does retrieval practice work", section="projects/learning")

    assert result.ungrounded == ["made-up-page"]
    assert "retrieval-practice" in result.pages_used
    assert "made-up-page" not in result.pages_used


def test_answer_grounded_citation_not_flagged(vault):
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["s1"]},
        "Retrieval practice strengthens long-term recall.",
    )
    provider = FakeProvider(
        answer_text="Retrieval practice strengthens recall. [[retrieval-practice]]"
    )
    result = answer(vault, provider, "how does retrieval practice work", section="projects/learning")

    assert result.ungrounded == []
    assert result.pages_used == ["retrieval-practice"]


def test_answer_save_writes_query_page(vault):
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["s1"]},
        "retrieval content",
    )
    provider = FakeProvider(answer_text="answer body")
    result = answer(vault, provider, "explain retrieval", section="projects/learning", save=True)
    assert result.saved_path is not None
    assert result.saved_path.exists()


def test_format_directive_is_format_specific():
    assert _format_directive("prose") == ""
    assert "table" in _format_directive("table").lower()
    assert "marp" in _format_directive("slides").lower()


def test_answer_slides_save_sets_marp_frontmatter(vault):
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["s1"]},
        "retrieval content",
    )
    provider = FakeProvider(answer_text="# Title\n\n---\n\nslide body")
    result = answer(
        vault, provider, "explain retrieval", section="projects/learning", save=True, fmt="slides"
    )
    assert result.saved_path is not None
    saved = read_page(result.saved_path)
    assert saved.metadata.get("marp") is True
