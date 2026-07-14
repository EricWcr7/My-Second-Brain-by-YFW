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
    assert "the" not in tokenize("the retrieval practice strengthens recall")
    assert "retrieval" in tokenize("the retrieval practice strengthens recall")


def test_section_contains_prefix_rule():
    # General (root) sees everything.
    assert section_contains("", "projects/learning")
    assert section_contains("", "")
    # A branch sees its whole subtree (and itself).
    assert section_contains("projects", "projects/learning")
    assert section_contains("projects", "projects")
    # A leaf sees only itself; siblings are isolated.
    assert section_contains("projects/learning", "projects/learning")
    assert not section_contains("projects/learning", "projects/planning")
    assert not section_contains("archive", "projects/learning")
    # Matching is on segment boundaries, not raw string prefix.
    assert not section_contains("projects", "projects-archive")


def test_search_ranks_relevant_page_first(vault):
    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "Retrieval practice strengthens recall and long-term memory.",
    )
    _add_concept(
        vault,
        "projects/learning",
        "Spaced Repetition",
        "A review schedule spaces practice over time.",
    )
    hits = search(vault, "retrieval practice recall", section="projects/learning")
    assert hits
    assert hits[0].ref.title == "Retrieval Practice"


def test_search_scope_is_prefix_based(vault):
    _add_concept(vault, "projects/learning", "Learning Review", "review the learning notes")
    _add_concept(vault, "projects/planning", "Project Review", "review project milestones")
    _add_concept(vault, "archive", "Archived Review", "review the archived summary")

    # A leaf scope sees only itself.
    learning = search(vault, "review", section="projects/learning")
    assert {h.ref.section for h in learning} == {"projects/learning"}

    # The Projects branch sees both child scopes, but not the archive sibling.
    projects = search(vault, "review", section="projects")
    assert {h.ref.section for h in projects} == {"projects/learning", "projects/planning"}

    # General (no scope) sees the whole knowledge base.
    everything = search(vault, "review")
    assert {h.ref.section for h in everything} == {
        "projects/learning",
        "projects/planning",
        "archive",
    }


# --- hybrid retrieval (RRF fusion) -------------------------------------------


def test_rrf_rewards_agreement_across_lists():
    scores = _rrf([["a", "b"], ["a", "c"]], k=60)
    # `a` appears in both ranked lists, so it outscores list-exclusive `b`/`c`.
    assert scores["a"] > scores["b"]
    assert scores["a"] > scores["c"]


def test_hybrid_fuses_keyword_and_vector(vault, monkeypatch):
    _add_concept(
        vault, "projects/learning", "Retrieval Practice", "retrieval practice recall memory"
    )
    _add_concept(
        vault, "projects/learning", "Spaced Repetition", "spaced repetition schedule"
    )
    _add_concept(vault, "projects/learning", "Feedback Loop", "feedback improves learning")

    # Stub the vector pass (no LanceDB): semantic ranking puts retrieval practice
    # first, then surfaces a page with no keyword overlap with the query.
    monkeypatch.setattr(
        search_mod, "_vector_page_list", lambda *a, **k: ["retrieval-practice", "feedback-loop"]
    )
    hits = search(vault, "retrieval", section="projects/learning", embedder=object())
    slugs = [h.ref.slug for h in hits]

    # The first page wins in both lists; feedback is recalled by vectors despite
    # zero keyword overlap — the headline hybrid benefit.
    assert slugs[0] == "retrieval-practice"
    assert "feedback-loop" in slugs


def test_search_without_embedder_is_pure_keyword(vault, monkeypatch):
    _add_concept(vault, "projects/learning", "Retrieval Practice", "retrieval practice")

    def _boom(*a, **k):  # the vector path must not run when embedder is None
        raise AssertionError("vector path should be skipped without an embedder")

    monkeypatch.setattr(search_mod, "_vector_page_list", _boom)
    hits = search(vault, "retrieval", section="projects/learning")
    assert [h.ref.slug for h in hits] == ["retrieval-practice"]


def test_vector_index_roundtrip_and_hybrid(vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall and memory",
    )
    _add_concept(vault, "projects/learning", "Sky", "the sunset sky colors at dusk")

    embedder = FakeEmbedder()
    result = reindex_all(vault, embedder)
    assert result.pages == 2 and result.chunks >= 2
    # Embeddings land in the model's table; embed() ran for the global model only.
    assert all(model == vault.embed_model for model, _ in embedder.calls)

    # A query whose words only overlap the learning page ranks it first via vectors.
    hits = search(vault, "retrieval recall", section="projects/learning", embedder=embedder)
    assert hits and hits[0].ref.slug == "retrieval-practice"

    # Incremental reindex re-embeds nothing when content is unchanged.
    again = reindex_all(vault, embedder)
    assert again.chunks == 0 and again.skipped == again.pages
