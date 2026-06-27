import pytest

from llmwiki import search as search_mod
from llmwiki import wiki
from llmwiki.search import _rrf, search, tokenize
from llmwiki.store import write_page
from llmwiki.wiki import section_contains
from tests.fakes import FakeEmbedder


def _add_concept(vault, section, title, body):
    write_page(
        wiki.concept_path(vault, section, title),
        {"title": title, "type": "concept", "section": section, "sources": ["s1"]},
        body,
    )


def test_tokenize_drops_stopwords_and_short():
    assert "the" not in tokenize("the gradient is a vector")
    assert "gradient" in tokenize("the gradient is a vector")


def test_section_contains_prefix_rule():
    # General (root) sees everything.
    assert section_contains("", "academic/calc")
    assert section_contains("", "")
    # A branch sees its whole subtree (and itself).
    assert section_contains("academic", "academic/calc")
    assert section_contains("academic", "academic")
    # A leaf sees only itself; siblings are isolated.
    assert section_contains("academic/calc", "academic/calc")
    assert not section_contains("academic/calc", "academic/stats")
    assert not section_contains("personal", "academic/calc")
    # Matching is on segment boundaries, not raw string prefix.
    assert not section_contains("academic", "academic-archive")


def test_search_ranks_relevant_page_first(vault):
    _add_concept(vault, "academic/calc", "Gradient", "The gradient is the vector of partial derivatives.")
    _add_concept(vault, "academic/calc", "Continuity", "A function is continuous if limits agree.")
    hits = search(vault, "gradient vector partial derivatives", section="academic/calc")
    assert hits
    assert hits[0].ref.title == "Gradient"


def test_search_scope_is_prefix_based(vault):
    _add_concept(vault, "academic/calc", "Gradient", "gradient vector field")
    _add_concept(vault, "academic/stats", "Gradient Descent", "gradient based optimization")
    _add_concept(vault, "personal", "Gradient Sky", "the gradient of the sunset sky")

    # A course sees only itself.
    calc = search(vault, "gradient", section="academic/calc")
    assert {h.ref.section for h in calc} == {"academic/calc"}

    # The Academic branch sees every course, but not the personal sibling.
    academic = search(vault, "gradient", section="academic")
    assert {h.ref.section for h in academic} == {"academic/calc", "academic/stats"}

    # General (no scope) sees the whole knowledge base.
    everything = search(vault, "gradient")
    assert {h.ref.section for h in everything} == {
        "academic/calc",
        "academic/stats",
        "personal",
    }


# --- hybrid retrieval (RRF fusion) -------------------------------------------


def test_rrf_rewards_agreement_across_lists():
    scores = _rrf([["a", "b"], ["a", "c"]], k=60)
    # `a` appears in both ranked lists, so it outscores list-exclusive `b`/`c`.
    assert scores["a"] > scores["b"]
    assert scores["a"] > scores["c"]


def test_hybrid_fuses_keyword_and_vector(vault, monkeypatch):
    _add_concept(vault, "academic/calc", "Gradient", "gradient vector partial derivatives")
    _add_concept(vault, "academic/calc", "Curl", "curl of a vector field")
    _add_concept(vault, "academic/calc", "Divergence", "divergence theorem and flux")

    # Stub the vector pass (no LanceDB): semantic ranking puts gradient first, then
    # surfaces divergence — a page with NO keyword overlap with the query.
    monkeypatch.setattr(
        search_mod, "_vector_page_list", lambda *a, **k: ["gradient", "divergence"]
    )
    hits = search(vault, "gradient", section="academic/calc", embedder=object())
    slugs = [h.ref.slug for h in hits]

    # `gradient` wins (in both keyword + vector lists); `divergence` is recalled by
    # the vector pass despite zero keyword match — the headline hybrid benefit.
    assert slugs[0] == "gradient"
    assert "divergence" in slugs


def test_search_without_embedder_is_pure_keyword(vault, monkeypatch):
    _add_concept(vault, "academic/calc", "Gradient", "gradient vector")

    def _boom(*a, **k):  # the vector path must not run when embedder is None
        raise AssertionError("vector path should be skipped without an embedder")

    monkeypatch.setattr(search_mod, "_vector_page_list", _boom)
    hits = search(vault, "gradient", section="academic/calc")
    assert [h.ref.slug for h in hits] == ["gradient"]


def test_vector_index_roundtrip_and_hybrid(vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all

    _add_concept(
        vault, "academic/calc", "Gradient",
        "gradient vector partial derivatives of a function",
    )
    _add_concept(vault, "academic/calc", "Sky", "the sunset sky colors at dusk")

    embedder = FakeEmbedder()
    result = reindex_all(vault, embedder)
    assert result.pages == 2 and result.chunks >= 2
    # Embeddings land in the model's table; embed() ran for the global model only.
    assert all(model == vault.embed_model for model, _ in embedder.calls)

    # A query whose words only overlap the Gradient page ranks it first via vectors.
    hits = search(vault, "gradient derivative", section="academic/calc", embedder=embedder)
    assert hits and hits[0].ref.slug == "gradient"

    # Incremental reindex re-embeds nothing when content is unchanged.
    again = reindex_all(vault, embedder)
    assert again.chunks == 0 and again.skipped == again.pages
