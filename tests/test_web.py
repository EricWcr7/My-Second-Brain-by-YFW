import pytest
from fastapi.testclient import TestClient

from llmwiki.ingest import (
    ConceptDraft,
    GenerationResult,
    SourceAnalysis,
    SourcePageDraft,
)
from llmwiki.store import (
    ensure_dir,
    load_state,
    read_page,
    save_state,
    set_source_record,
    write_page,
)
from llmwiki.web.app import SUPPORTED_EXTS, create_app
from llmwiki.wiki import concept_path, source_path

from tests.fakes import FakeProvider


def _seed(vault):
    write_page(
        concept_path(vault, "academic/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "academic/learning", "sources": ["learning-notes"]},
        "A review ratio can be written as $r = c \\div d$. See [[feedback-loop]].\n",
    )
    write_page(
        source_path(vault, "academic/learning", "learning-notes"),
        {"title": "Learning Notes", "type": "source", "section": "academic/learning"},
        "Workshop notes for retrieval practice.\n",
    )


@pytest.fixture
def client(vault):
    _seed(vault)
    fake = FakeProvider(answer_text="Retrieval practice improves recall. [[retrieval-practice]]")
    app = create_app(vault, provider_factory=lambda cfg: fake)
    return TestClient(app)


def test_pages_lists_concepts_and_sources(client):
    pages = client.get("/api/pages").json()
    by_slug = {p["slug"]: p for p in pages}
    assert by_slug["retrieval-practice"]["type"] == "concept"
    assert by_slug["learning-notes"]["type"] == "source"


def test_page_hit_preserves_latex_and_miss_is_404(client):
    ok = client.get("/api/page/retrieval-practice")
    assert ok.status_code == 200
    assert ok.json()["title"] == "Retrieval Practice"
    assert "\\div" in ok.json()["content"]  # LaTeX kept verbatim for the UI to render
    assert client.get("/api/page/nope").status_code == 404


def test_search_ranks_the_concept(client):
    hits = client.get("/api/search", params={"q": "retrieval practice"}).json()
    assert hits[0]["slug"] == "retrieval-practice"
    assert hits[0]["score"] > 0
    assert hits[0]["section"] == "academic/learning"


def test_meta_reports_sections(client):
    meta = client.get("/api/meta").json()
    # Sections come from pages *and* directories, so the seeded academic branch
    # shows up even before anything is filed in it.
    assert meta["sections"] == ["academic", "academic/learning"]
    assert meta["default_section"] == ""


def test_meta_and_routes_exclude_removed_feature(client):
    removed_prefix = "sol" + "ver"
    meta = client.get("/api/meta").json()
    assert not any(key.startswith(removed_prefix) for key in meta)
    assert client.get(f"/api/{removed_prefix}/sessions").status_code == 404


def test_create_section_scaffolds_dirs(client, vault):
    r = client.post("/api/sections", json={"name": "Learning Lab", "parent": "academic"})
    assert r.status_code == 200
    # Case is preserved now: "Learning Lab" -> "Learning-Lab".
    assert r.json()["section"] == "academic/Learning-Lab"
    assert (vault.concepts_dir / "academic" / "Learning-Lab").is_dir()
    assert (vault.source_pages_dir / "academic" / "Learning-Lab").is_dir()
    # The new project is now visible in the section list.
    assert "academic/Learning-Lab" in client.get("/api/meta").json()["sections"]


def test_create_section_preserves_case(client, vault):
    r = client.post("/api/sections", json={"name": "LearningLab ", "parent": "academic"})
    assert r.status_code == 200
    assert r.json()["section"] == "academic/LearningLab"
    assert (vault.concepts_dir / "academic" / "LearningLab").is_dir()
    assert (vault.source_pages_dir / "academic" / "LearningLab").is_dir()


def test_create_section_keeps_unicode(client, vault):
    r = client.post("/api/sections", json={"name": "学习方法", "parent": "academic"})
    assert r.status_code == 200
    assert r.json()["section"] == "academic/学习方法"
    assert (vault.concepts_dir / "academic" / "学习方法").is_dir()
    assert "academic/学习方法" in client.get("/api/meta").json()["sections"]


def test_create_section_rejects_duplicate_and_blank(client):
    assert client.post("/api/sections", json={"name": "Learning", "parent": "academic"}).status_code == 409
    # Case-insensitive: this collides with the seeded academic/learning scope.
    assert client.post("/api/sections", json={"name": "LEARNING", "parent": "academic"}).status_code == 409
    assert client.post("/api/sections", json={"name": "   ", "parent": "academic"}).status_code == 422


def test_create_top_level_branch_at_general_root(client, vault):
    # A top-level branch (parent="" → the General root) is creatable from the web
    # UI, appears beside the seeded Academic branch, and — unlike Academic — is
    # deletable (not protected).
    r = client.post("/api/sections", json={"name": "Projects", "parent": ""})
    assert r.status_code == 200
    assert r.json()["section"] == "Projects"
    assert (vault.concepts_dir / "Projects").is_dir()
    assert (vault.source_pages_dir / "Projects").is_dir()
    assert "Projects" in client.get("/api/meta").json()["sections"]
    assert client.delete("/api/sections/Projects").status_code == 200
    assert "Projects" not in client.get("/api/meta").json()["sections"]


def test_delete_section_removes_dirs(client, vault):
    client.post("/api/sections", json={"name": "LearningLab", "parent": "academic"})
    r = client.delete("/api/sections/academic/LearningLab")
    assert r.status_code == 200
    assert r.json()["section"] == "academic/LearningLab"
    assert not (vault.concepts_dir / "academic" / "LearningLab").exists()
    assert not (vault.source_pages_dir / "academic" / "LearningLab").exists()
    assert "academic/LearningLab" not in client.get("/api/meta").json()["sections"]


def test_delete_section_wipes_ledger_cache_raw_and_overrides(client, vault):
    # Deleting a section must leave nothing behind: not just the pages, but the
    # ledger record, its normalized cache + raw bytes, and per-section overrides.
    section = "academic/LearningLab"
    client.post("/api/sections", json={"name": "LearningLab", "parent": "academic"})

    write_page(
        concept_path(vault, section, "Review Schedule"),
        {"title": "Review Schedule", "type": "concept", "section": section, "sources": ["handbook"]},
        "The schedule spaces reviews over time.\n",
    )
    checksum = "deadbeef"
    raw_ref = "raw/sources/handbook.pdf"
    ensure_dir(vault.normalized_dir)
    (vault.normalized_dir / f"{checksum}.md").write_text("normalized\n", "utf-8")
    ensure_dir((vault.root / raw_ref).parent)
    (vault.root / raw_ref).write_text("%PDF fake\n", "utf-8")
    state = load_state(vault)
    set_source_record(
        state, raw_ref, {"checksum": checksum, "section": section, "raw_ref": raw_ref}
    )
    save_state(vault, state)
    override = vault.section_overrides_dir / "academic" / "LearningLab" / "purpose.md"
    ensure_dir(override.parent)
    override.write_text("project-specific purpose\n", "utf-8")

    assert client.delete(f"/api/sections/{section}").status_code == 200

    assert not (vault.concepts_dir / "academic" / "LearningLab").exists()
    assert not (vault.normalized_dir / f"{checksum}.md").exists()
    assert not (vault.root / raw_ref).exists()
    assert not (vault.section_overrides_dir / "academic" / "LearningLab").exists()
    assert load_state(vault).get("sources", {}) == {}


def test_delete_section_keeps_other_sections_intact(client, vault):
    # A sibling section's ledger record and bytes must survive the delete.
    client.post("/api/sections", json={"name": "LearningLab", "parent": "academic"})
    keep_checksum = "cafef00d"
    keep_ref = "raw/sources/keep.pdf"
    ensure_dir(vault.normalized_dir)
    (vault.normalized_dir / f"{keep_checksum}.md").write_text("keep\n", "utf-8")
    state = load_state(vault)
    set_source_record(
        state,
        keep_ref,
        {"checksum": keep_checksum, "section": "academic/learning", "raw_ref": keep_ref},
    )
    save_state(vault, state)

    assert client.delete("/api/sections/academic/LearningLab").status_code == 200

    assert (vault.normalized_dir / f"{keep_checksum}.md").exists()
    assert keep_ref in load_state(vault).get("sources", {})


def test_delete_section_purges_vector_index(client, vault):
    # The deleted concepts' chunks must leave the vector index too, or semantic
    # search would still surface a page that no longer exists on disk.
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    from tests.fakes import FakeEmbedder

    client.post("/api/sections", json={"name": "LearningLab", "parent": "academic"})
    write_page(
        concept_path(vault, "academic/LearningLab", "Review Schedule"),
        {"title": "Review Schedule", "type": "concept", "section": "academic/LearningLab", "sources": ["handbook"]},
        "Review intervals and checkpoints in a learning plan.\n",
    )
    reindex_all(vault, FakeEmbedder())

    def stored_slugs():
        return {slug for _, slug in open_index(vault).stored_pages(vault.embed_model)}

    assert "review-schedule" in stored_slugs()  # indexed before delete

    assert client.delete("/api/sections/academic/LearningLab").status_code == 200

    assert "review-schedule" not in stored_slugs()  # vectors dropped with the page


def test_delete_section_protects_roots(client, vault):
    assert client.delete("/api/sections/academic").status_code == 403
    assert (vault.concepts_dir / "academic").is_dir()


def test_delete_section_missing_returns_404(client):
    assert client.delete("/api/sections/academic/nope").status_code == 404


def test_delete_concept_page_removes_file_and_ledger_survives(client, vault):
    # A concept delete removes the page and its index entry but leaves the
    # ledger alone — the wiki pages, not the ledger, gate re-ingest.
    state = load_state(vault)
    set_source_record(
        state,
        "raw/sources/learning-notes.md",
        {"checksum": "feedface", "section": "academic/learning", "source_slug": "learning-notes"},
    )
    save_state(vault, state)

    r = client.delete(
        "/api/page/retrieval-practice", params={"type": "concept", "section": "academic/learning"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "retrieval-practice" and body["type"] == "concept"
    assert body["scrubbed"] == [] and body["removed_concepts"] == []
    assert not concept_path(vault, "academic/learning", "Retrieval Practice").exists()
    assert client.get("/api/page/retrieval-practice").status_code == 404
    assert "retrieval-practice" not in vault.index_file.read_text("utf-8")
    assert "raw/sources/learning-notes.md" in load_state(vault)["sources"]
    assert "delete |" in vault.log_file.read_text("utf-8")  # journaled


def test_delete_concept_purges_vector_index(client, vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    from tests.fakes import FakeEmbedder

    reindex_all(vault, FakeEmbedder())

    def stored_slugs():
        return {slug for _, slug in open_index(vault).stored_pages(vault.embed_model)}

    assert "retrieval-practice" in stored_slugs()

    r = client.delete(
        "/api/page/retrieval-practice", params={"type": "concept", "section": "academic/learning"}
    )
    assert r.status_code == 200

    assert "retrieval-practice" not in stored_slugs()


def test_delete_concept_preserves_same_slug_vectors_in_sibling_section(client, vault):
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    from tests.fakes import FakeEmbedder

    write_page(
        concept_path(vault, "academic/other", "Retrieval Practice"),
        {
            "title": "Retrieval Practice",
            "type": "concept",
            "section": "academic/other",
            "sources": ["other-source"],
        },
        "A sibling section's retrieval practice page.\n",
    )
    reindex_all(vault, FakeEmbedder())
    index = open_index(vault)
    assert index.stored_pages(vault.embed_model) == {
        ("academic/learning", "retrieval-practice"),
        ("academic/other", "retrieval-practice"),
    }

    response = client.delete(
        "/api/page/retrieval-practice",
        params={"type": "concept", "section": "academic/learning"},
    )

    assert response.status_code == 200
    assert index.stored_pages(vault.embed_model) == {
        ("academic/other", "retrieval-practice")
    }


def test_delete_source_page_full_teardown(client, vault):
    # A source delete takes its ledger record, normalized cache, and raw bytes
    # with it; a record for another section survives untouched.
    checksum = "deadbeef"
    raw_ref = "raw/sources/learning-notes.md"
    ensure_dir(vault.normalized_dir)
    (vault.normalized_dir / f"{checksum}.md").write_text("normalized\n", "utf-8")
    ensure_dir((vault.root / raw_ref).parent)
    (vault.root / raw_ref).write_text("# Learning Notes\n", "utf-8")
    keep_checksum = "cafef00d"
    keep_ref = "raw/sources/keep.pdf"
    (vault.normalized_dir / f"{keep_checksum}.md").write_text("keep\n", "utf-8")
    state = load_state(vault)
    set_source_record(
        state,
        raw_ref,
        {"checksum": checksum, "section": "academic/learning", "raw_ref": raw_ref, "source_slug": "learning-notes"},
    )
    set_source_record(
        state,
        keep_ref,
        {"checksum": keep_checksum, "section": "academic/other", "raw_ref": keep_ref, "source_slug": "keep"},
    )
    save_state(vault, state)

    r = client.delete(
        "/api/page/learning-notes", params={"type": "source", "section": "academic/learning"}
    )
    assert r.status_code == 200
    assert not source_path(vault, "academic/learning", "learning-notes").exists()
    assert not (vault.normalized_dir / f"{checksum}.md").exists()
    assert not (vault.root / raw_ref).exists()
    remaining = load_state(vault)["sources"]
    assert raw_ref not in remaining and keep_ref in remaining
    assert (vault.normalized_dir / f"{keep_checksum}.md").exists()


def test_delete_source_scrubs_provenance_keeps_concept(client, vault):
    # A concept grounded by two sources survives, losing only the deleted entry.
    write_page(
        concept_path(vault, "academic/learning", "Retrieval Practice"),
        {
            "title": "Retrieval Practice",
            "type": "concept",
            "section": "academic/learning",
            "sources": ["learning-notes", "workshop-notes"],
        },
        "Body stays intact.\n",
    )

    r = client.delete(
        "/api/page/learning-notes", params={"type": "source", "section": "academic/learning"}
    )
    assert r.status_code == 200
    assert r.json()["scrubbed"] == ["retrieval-practice"]
    assert r.json()["removed_concepts"] == []
    page = read_page(concept_path(vault, "academic/learning", "Retrieval Practice"))
    assert page is not None
    assert page.metadata["sources"] == ["workshop-notes"]
    assert page.metadata["title"] == "Retrieval Practice"
    assert "Body stays intact." in page.content


def test_delete_source_cascades_orphaned_concept(client, vault):
    # The seeded retrieval-practice's only provenance is learning-notes, so deleting the
    # source deletes the concept too. learning-notes has no ledger record — proving a
    # ledger-less source still deletes cleanly.
    r = client.delete(
        "/api/page/learning-notes", params={"type": "source", "section": "academic/learning"}
    )
    assert r.status_code == 200
    assert r.json()["removed_concepts"] == ["retrieval-practice"]
    assert not concept_path(vault, "academic/learning", "Retrieval Practice").exists()
    assert not source_path(vault, "academic/learning", "learning-notes").exists()
    idx = vault.index_file.read_text("utf-8")
    assert "retrieval-practice" not in idx and "learning-notes" not in idx


def test_delete_source_cascade_purges_vectors(client, vault):
    # The cascade-deleted concept's chunks must leave the vector index too.
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    from tests.fakes import FakeEmbedder

    reindex_all(vault, FakeEmbedder())

    def stored_slugs():
        return {slug for _, slug in open_index(vault).stored_pages(vault.embed_model)}

    assert "retrieval-practice" in stored_slugs()

    r = client.delete(
        "/api/page/learning-notes", params={"type": "source", "section": "academic/learning"}
    )
    assert r.status_code == 200
    assert r.json()["removed_concepts"] == ["retrieval-practice"]

    assert "retrieval-practice" not in stored_slugs()


def test_delete_source_leaves_other_sections_alone(client, vault):
    # A same-slug source and its dependent concept in a sibling section are
    # untouched: sources: entries are bare slugs, so cross-section scrubbing
    # could hit the wrong reference.
    write_page(
        source_path(vault, "academic/other", "learning-notes"),
        {"title": "Learning Notes (other)", "type": "source", "section": "academic/other"},
        "Notes from another project.\n",
    )
    write_page(
        concept_path(vault, "academic/other", "Feedback Loop"),
        {
            "title": "Feedback Loop",
            "type": "concept",
            "section": "academic/other",
            "sources": ["learning-notes"],
        },
        "Feedback Loop body.\n",
    )

    r = client.delete(
        "/api/page/learning-notes", params={"type": "source", "section": "academic/learning"}
    )
    assert r.status_code == 200
    assert source_path(vault, "academic/other", "learning-notes").exists()
    page = read_page(concept_path(vault, "academic/other", "Feedback Loop"))
    assert page is not None
    assert page.metadata["sources"] == ["learning-notes"]


def test_delete_page_404_variants(client):
    params = {"type": "concept", "section": "academic/learning"}
    assert client.delete("/api/page/nope", params=params).status_code == 404
    assert (
        client.delete(
            "/api/page/retrieval-practice", params={"type": "concept", "section": "academic/other"}
        ).status_code
        == 404
    )
    # Type mismatch: retrieval-practice is a concept, not a source.
    assert (
        client.delete(
            "/api/page/retrieval-practice", params={"type": "source", "section": "academic/learning"}
        ).status_code
        == 404
    )


def test_delete_page_invalid_type_422(client):
    assert (
        client.delete(
            "/api/page/retrieval-practice", params={"type": "bogus", "section": "academic/learning"}
        ).status_code
        == 422
    )


def test_search_section_scope(client):
    # The Academic branch sees the project page; a sibling section does not.
    assert client.get("/api/search", params={"q": "retrieval practice", "section": "academic"}).json()
    assert client.get("/api/search", params={"q": "retrieval practice", "section": "projects"}).json() == []


def test_overrides_list_reports_status_and_general(client):
    data = client.get("/api/overrides").json()
    assert set(data["components"]) == {
        "ingest_analysis", "ingest_generation", "answer", "lint", "purpose", "schema"
    }
    assert "knowledge base" in data["general"]["answer"]  # the general default text
    by_section = {s["section"]: s for s in data["sections"]}
    assert "academic/learning" in by_section
    assert set(by_section["academic/learning"]["status"].values()) == {"general"}


def test_overrides_set_get_and_reset(client):
    r = client.post("/api/overrides", json={"sections": ["academic/learning"], "set": {"answer": "CUSTOM"}})
    assert r.status_code == 200
    assert r.json()["updated"][0]["status"]["answer"] == "override"

    got = client.get("/api/overrides/academic/learning").json()
    assert got["components"]["answer"]["override"] == "CUSTOM"
    assert got["components"]["answer"]["effective"] == "CUSTOM"
    assert got["components"]["lint"]["override"] is None  # untouched components inherit

    r2 = client.post("/api/overrides", json={"sections": ["academic/learning"], "reset": ["answer"]})
    assert r2.json()["updated"][0]["status"]["answer"] == "general"
    assert client.get("/api/overrides/academic/learning").json()["components"]["answer"]["override"] is None


def test_overrides_multi_section_apply(client):
    # One edit fans out to several branches at once.
    r = client.post("/api/overrides", json={"sections": ["academic", "academic/learning"], "set": {"purpose": "P"}})
    assert r.status_code == 200
    statuses = {u["section"]: u["status"]["purpose"] for u in r.json()["updated"]}
    assert statuses == {"academic": "override", "academic/learning": "override"}


def test_overrides_unknown_section_404_and_component_422(client):
    assert client.post(
        "/api/overrides", json={"sections": ["does/not/exist"], "set": {"answer": "x"}}
    ).status_code == 404
    assert client.post(
        "/api/overrides", json={"sections": ["academic/learning"], "set": {"bogus": "x"}}
    ).status_code == 422


def test_home_returns_content(client):
    assert "content" in client.get("/api/home").json()


def test_home_is_scope_aware(client, monkeypatch):
    # Refreshing the project overview, then asking /api/home for that scope, serves
    # the section's own overview (not the global one).
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert client.post("/api/overview/refresh", json={"section": "academic/learning"}).status_code == 200
    body = client.get("/api/home", params={"section": "academic/learning"}).json()
    assert "retrieval practice" in body["content"].lower()


def test_overview_refresh_requires_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/api/overview/refresh", json={"section": "academic/learning"})
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_lint_flags_dangling_wikilink(client):
    issues = client.get("/api/lint").json()
    assert any("feedback-loop" in i["message"] for i in issues)


def test_query_with_key(client, monkeypatch):
    # Default provider is OpenAI, so its key is what enables Ask.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # /api/query is multipart now (it can carry file attachments), so send form data.
    r = client.post("/api/query", data={"question": "state retrieval practice"})
    assert r.status_code == 200
    assert "retrieval practice" in r.json()["answer"].lower()
    assert "retrieval-practice" in r.json()["pages_used"] or r.json()["pages_used"] == []


def test_query_surfaces_ungrounded_citations(vault, monkeypatch):
    # The /api/query contract exposes invented citations so the Ask view can warn.
    _seed(vault)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake = FakeProvider(answer_text="As shown in [[retrieval-practice]] and [[ghost-page]].")
    c = TestClient(create_app(vault, provider_factory=lambda cfg: fake))
    body = c.post("/api/query", data={"question": "anything"}).json()
    assert body["ungrounded"] == ["ghost-page"]
    assert "retrieval-practice" in body["pages_used"]


def test_query_provider_error_returns_503(vault, monkeypatch):
    # A model failure mid-answer must render as a clean 503, not a 500 traceback.
    from llmwiki.providers import ProviderError

    _seed(vault)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _Boom(FakeProvider):
        def complete(self, *a, **k):
            raise ProviderError("model exploded")

    c = TestClient(create_app(vault, provider_factory=lambda cfg: _Boom()))
    r = c.post("/api/query", data={"question": "anything"})
    assert r.status_code == 503
    assert "model exploded" in r.json()["detail"]


def test_query_without_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/api/query", data={"question": "anything"})
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_key_check_follows_configured_provider(vault, monkeypatch):
    # With provider=anthropic, the Anthropic key (not OpenAI) enables Ask.
    _seed(vault)
    vault.provider = "anthropic"
    fake = FakeProvider(answer_text="ok [[retrieval-practice]]")
    client = TestClient(create_app(vault, provider_factory=lambda cfg: fake))

    assert client.get("/api/meta").json()["api_key_env"] == "ANTHROPIC_API_KEY"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert client.post("/api/query", data={"question": "anything"}).status_code == 200


# --- ingest endpoint + Ask attachments --------------------------------------


def _ingest_provider() -> FakeProvider:
    """A fake wired with the analysis + generation passes ingest() needs."""
    analysis = SourceAnalysis(
        source_title="Learning Notes",
        source_summary="Notes on retrieval practice.",
        concept_titles=["Retrieval Practice"],
    )
    generation = GenerationResult(
        concept_pages=[ConceptDraft(title="Retrieval Practice", body="Frequent recall strengthens memory.")],
        source_page=SourcePageDraft(summary="A short note.", grounds=["Retrieval Practice"]),
        log_entry="Ingested retrieval practice notes.",
    )
    return FakeProvider(analysis=analysis, generation=generation)


@pytest.fixture
def ingest_client(vault):
    _seed(vault)
    return TestClient(create_app(vault, provider_factory=lambda cfg: _ingest_provider()))


def test_meta_includes_supported_exts(client):
    exts = client.get("/api/meta").json()["supported_exts"]
    assert exts == SUPPORTED_EXTS
    assert ".pdf" in exts and ".md" in exts and ".png" in exts  # the UI's accept filter


def test_ingest_file_creates_pages_in_scope(ingest_client, vault, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = ingest_client.post(
        "/api/ingest",
        data={"section": "academic/learning"},
        files={"file": ("note.md", b"# Retrieval Practice\n\nRetrieval practice.", "text/markdown")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ingested"
    assert body["section"] == "academic/learning"
    assert body["concept_slugs"] == ["retrieval-practice"]
    # Pages were written under the requested scope, and the file copied into raw/.
    assert read_page(concept_path(vault, "academic/learning", "Retrieval Practice")) is not None
    assert read_page(source_path(vault, "academic/learning", "note")) is not None
    assert (vault.sources_dir / "note.md").exists()


def test_ingest_general_scope_files_into_root(ingest_client, vault, monkeypatch):
    # The General scope is the root: a missing/empty section files into "", never
    # the configured default_section.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = ingest_client.post(
        "/api/ingest",
        files={"file": ("root-note.md", b"# Retrieval Practice\n\nbody", "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["section"] == ""
    assert read_page(source_path(vault, "", "root-note")) is not None


def test_ingest_user_prompt_reaches_provider(vault, monkeypatch):
    # The optional guidance box on the Ingest form rides through to the model's
    # compile passes (parse calls) and is journaled for provenance.
    _seed(vault)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    seen: list[str] = []

    class _Recording(FakeProvider):
        def parse(self, system, user, schema, *, model=None, max_tokens=16000):
            seen.append(user)
            return super().parse(system, user, schema, model=model, max_tokens=max_tokens)

    fake = _Recording(
        analysis=SourceAnalysis(
            source_title="Learning Notes",
            source_summary="Notes on retrieval practice.",
            concept_titles=["Retrieval Practice"],
        ),
        generation=GenerationResult(
            concept_pages=[ConceptDraft(title="Retrieval Practice", body="Retrieval practice body.")],
            source_page=SourcePageDraft(summary="A short note.", grounds=["Retrieval Practice"]),
            log_entry="Ingested retrieval practice notes.",
        ),
    )
    app_client = TestClient(create_app(vault, provider_factory=lambda cfg: fake))
    r = app_client.post(
        "/api/ingest",
        data={"section": "academic/learning", "prompt": "focus on practical examples"},
        files={"file": ("note.md", b"# Retrieval Practice\n\nbody", "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert any("focus on practical examples" in u for u in seen)
    assert "guidance: focus on practical examples" in vault.log_file.read_text("utf-8")


def test_ingest_requires_api_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post(
        "/api/ingest",
        data={"section": "academic/learning"},
        files={"file": ("note.md", b"# x", "text/markdown")},
    )
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_ingest_requires_file_or_url(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert client.post("/api/ingest", data={"section": "academic/learning"}).status_code == 422


def test_reingest_after_concept_delete(ingest_client, vault, monkeypatch):
    # Deleting a concept page makes its source re-ingestable: the skip check
    # follows the wiki, and the page delete left the ledger record in place.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    files = {"file": ("note.md", b"# Retrieval Practice\n\nbody", "text/markdown")}

    first = ingest_client.post("/api/ingest", data={"section": "academic/learning"}, files=files)
    assert first.status_code == 200 and first.json()["status"] == "ingested"

    r = ingest_client.delete(
        "/api/page/retrieval-practice", params={"type": "concept", "section": "academic/learning"}
    )
    assert r.status_code == 200

    again = ingest_client.post("/api/ingest", data={"section": "academic/learning"}, files=files)
    assert again.status_code == 200 and again.json()["status"] == "ingested"


def test_query_attachment_reaches_provider(vault, monkeypatch):
    # An uploaded file in Ask becomes transient context in the model prompt.
    _seed(vault)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured: dict = {}

    class _Recording(FakeProvider):
        def complete(self, system, user, *, model=None, max_tokens=16000):
            captured["user"] = user
            return super().complete(system, user, model=model, max_tokens=max_tokens)

    fake = _Recording(answer_text="Answer drawing on the attachment.")
    app_client = TestClient(create_app(vault, provider_factory=lambda cfg: fake))
    r = app_client.post(
        "/api/query",
        data={"question": "summarize the attachment"},
        files={"files": ("ctx.md", b"UNIQUE_ATTACHMENT_MARKER in the file", "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert "UNIQUE_ATTACHMENT_MARKER" in captured["user"]
