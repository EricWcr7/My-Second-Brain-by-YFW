import logging

import pytest

from llmwiki import search as search_mod
from llmwiki import wiki
from llmwiki.providers import ProviderError
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
        search_mod,
        "_vector_page_list",
        lambda *a, **k: [
            "projects/learning/retrieval-practice",
            "projects/learning/feedback-loop",
        ],
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


def test_semantic_search_reconciles_out_of_band_page_changes(vault):
    pytest.importorskip("lancedb")
    from llmwiki.vectorindex import open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice recall memory",
    )
    _add_concept(vault, "projects/learning", "Sky", "sunset sky colors")
    embedder = FakeEmbedder()
    search(vault, "retrieval", section="projects/learning", embedder=embedder)

    # Simulate a Git/worktree update: one page changes, one appears, and one is
    # deleted without going through an llmwiki mutation pipeline.
    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    _add_concept(
        vault,
        "projects/learning",
        "Feedback Loop",
        "feedback improves learning",
    )
    wiki.concept_path(vault, "projects/learning", "Sky").unlink()

    embedder.calls.clear()
    hits = search(
        vault,
        "feedback learning",
        section="projects/learning",
        embedder=embedder,
    )

    assert hits and hits[0].ref.slug == "feedback-loop"
    assert open_index(vault).stored_pages(vault.embed_model) == {
        ("projects/learning", "feedback-loop"),
        ("projects/learning", "retrieval-practice"),
    }
    # Two changed/new pages were embedded, followed by the query itself.
    assert [count for _, count in embedder.calls] == [1, 1, 1]

    embedder.calls.clear()
    search(
        vault,
        "feedback learning",
        section="projects/learning",
        embedder=embedder,
    )
    assert embedder.calls == [(vault.embed_model, 1)]  # query only; pages unchanged


def test_semantic_search_reconciles_only_the_requested_scope(vault):
    pytest.importorskip("lancedb")
    from llmwiki.vectorindex import open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice recall",
    )
    _add_concept(
        vault,
        "archive",
        "Unrelated",
        "never-embed-out-of-scope",
    )

    class ScopedEmbedder(FakeEmbedder):
        def embed(self, texts, *, model):
            if any("never-embed-out-of-scope" in text for text in texts):
                raise AssertionError("out-of-scope concept was sent for embedding")
            return super().embed(texts, model=model)

    embedder = ScopedEmbedder()
    hits = search(
        vault,
        "retrieval practice",
        section="projects/learning",
        embedder=embedder,
    )

    assert hits and hits[0].ref.slug == "retrieval-practice"
    assert open_index(vault).stored_pages(vault.embed_model) == {
        ("projects/learning", "retrieval-practice")
    }
    assert [count for _, count in embedder.calls] == [1, 1]  # page + query


def test_semantic_search_keeps_same_slug_pages_in_separate_sections(vault):
    pytest.importorskip("lancedb")
    from llmwiki.vectorindex import open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    _add_concept(
        vault,
        "projects/planning",
        "Retrieval Practice",
        "retrieval practice for project reviews",
    )

    hits = search(vault, "retrieval practice", section="projects", embedder=FakeEmbedder())

    assert {(hit.ref.section, hit.ref.slug) for hit in hits} == {
        ("projects/learning", "retrieval-practice"),
        ("projects/planning", "retrieval-practice"),
    }
    assert open_index(vault).stored_pages(vault.embed_model) == {
        ("projects/learning", "retrieval-practice"),
        ("projects/planning", "retrieval-practice"),
    }


def test_reconcile_failure_warns_once_and_falls_back_to_bm25(
    vault, monkeypatch, caplog
):
    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )

    def fail_reconcile(*args, **kwargs):
        raise ProviderError("simulated embedding outage")

    monkeypatch.setattr(search_mod, "reindex_scope", fail_reconcile, raising=False)
    monkeypatch.setattr(search_mod, "_last_vector_warning", None, raising=False)
    with caplog.at_level(logging.WARNING, logger="llmwiki.search"):
        first = search(vault, "retrieval", embedder=FakeEmbedder())
        second = search(vault, "retrieval", embedder=FakeEmbedder())

    assert [hit.ref.slug for hit in first] == ["retrieval-practice"]
    assert [hit.ref.slug for hit in second] == ["retrieval-practice"]
    warnings = [record for record in caplog.records if "BM25" in record.message]
    assert len(warnings) == 1


def test_invalid_embedding_response_preserves_existing_page_rows(vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    reindex_all(vault, FakeEmbedder())
    index = open_index(vault)
    before = index.rows(vault.embed_model)

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "changed retrieval practice content",
    )

    class ShortEmbedder(FakeEmbedder):
        def embed(self, texts, *, model):
            return []

    with pytest.raises(ProviderError, match="returned 0 vectors for 1 chunks"):
        reindex_all(vault, ShortEmbedder())

    assert index.rows(vault.embed_model) == before


def test_legacy_bare_slug_rows_migrate_on_semantic_search(vault):
    pytest.importorskip("lancedb")
    from llmwiki.chunking import chunk_page
    from llmwiki.store import read_page
    from llmwiki.vectorindex import model_table_name, open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    ref = wiki.iter_pages(vault, "concept")[0]
    page = read_page(ref.path)
    chunk = chunk_page(ref, page.content, max_chars=vault.chunk_max_chars)[0]
    embedder = FakeEmbedder()
    vector = embedder.embed([chunk.embed_text()], model=vault.embed_model)[0]
    legacy = {
        "id": "retrieval-practice#0",
        "page_slug": "retrieval-practice",
        "section": "projects/learning",
        "page_title": "Retrieval Practice",
        "heading": "",
        "content_hash": chunk.content_hash,
        "vector": vector,
    }
    index = open_index(vault)
    index.db.create_table(model_table_name(vault.embed_model), data=[legacy])

    embedder.calls.clear()
    search(vault, "retrieval", section="projects/learning", embedder=embedder)

    assert set(index.existing_records(vault.embed_model)) == {
        "projects/learning/retrieval-practice#0"
    }
    assert [count for _, count in embedder.calls] == [1, 1]  # migrated page + query


def test_atomic_merge_preserves_rows_when_lancedb_rejects_vector_dimension(vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    reindex_all(vault, FakeEmbedder())
    index = open_index(vault)
    before = index.rows(vault.embed_model)
    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "changed retrieval practice content",
    )

    class WrongDimensionEmbedder(FakeEmbedder):
        def embed(self, texts, *, model):
            return [[1.0] for _ in texts]

    with pytest.raises(Exception):
        reindex_all(vault, WrongDimensionEmbedder())

    assert index.rows(vault.embed_model) == before


def test_reindex_detects_and_repairs_duplicate_chunk_ids(vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import (
        DuplicateChunkIDsError,
        model_table_name,
        open_index,
    )

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    reindex_all(vault, FakeEmbedder())
    index = open_index(vault)
    duplicate = index.rows(vault.embed_model)[0]
    index.db.open_table(model_table_name(vault.embed_model)).add([duplicate])

    with pytest.raises(DuplicateChunkIDsError, match="1 duplicate chunk id"):
        index.existing_records(vault.embed_model)

    embedder = FakeEmbedder()
    result = reindex_all(vault, embedder)

    assert result.chunks == 1 and result.skipped == 0
    assert len(index.rows(vault.embed_model)) == 1
    assert set(index.existing_records(vault.embed_model)) == {
        "projects/learning/retrieval-practice#0"
    }


def test_duplicate_repair_preserves_rows_when_vector_dimension_is_wrong(vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import model_table_name, open_index

    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "retrieval practice strengthens recall",
    )
    reindex_all(vault, FakeEmbedder())
    index = open_index(vault)
    table = index.db.open_table(model_table_name(vault.embed_model))
    table.add([index.rows(vault.embed_model)[0]])
    before = index.rows(vault.embed_model)
    before_schema = table.schema
    _add_concept(
        vault,
        "projects/learning",
        "Retrieval Practice",
        "changed retrieval practice content",
    )

    class WrongDimensionEmbedder(FakeEmbedder):
        def embed(self, texts, *, model):
            return [[1.0] for _ in texts]

    with pytest.raises(
        ValueError, match="do not match the existing vector index schema"
    ):
        reindex_all(vault, WrongDimensionEmbedder())

    assert index.rows(vault.embed_model) == before
    assert index.db.open_table(model_table_name(vault.embed_model)).schema == before_schema
