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
        concept_path(vault, "academic/calc", "Chain Rule"),
        {"title": "Chain Rule", "type": "concept", "section": "academic/calc", "sources": ["lecture-1"]},
        "If $h = f \\circ g$ then $h'(x) = f'(g(x))\\,g'(x)$. See [[gradient]].\n",
    )
    write_page(
        source_path(vault, "academic/calc", "lecture-1"),
        {"title": "Lecture 1", "type": "source", "section": "academic/calc"},
        "Lecture notes for the chain rule.\n",
    )


@pytest.fixture
def client(vault):
    _seed(vault)
    fake = FakeProvider(answer_text="The chain rule: $h' = f'(g)\\,g'$. [[chain-rule]]")
    app = create_app(vault, provider_factory=lambda cfg: fake)
    return TestClient(app)


def test_pages_lists_concepts_and_sources(client):
    pages = client.get("/api/pages").json()
    by_slug = {p["slug"]: p for p in pages}
    assert by_slug["chain-rule"]["type"] == "concept"
    assert by_slug["lecture-1"]["type"] == "source"


def test_page_hit_preserves_latex_and_miss_is_404(client):
    ok = client.get("/api/page/chain-rule")
    assert ok.status_code == 200
    assert ok.json()["title"] == "Chain Rule"
    assert "\\circ" in ok.json()["content"]  # LaTeX kept verbatim for the UI to render
    assert client.get("/api/page/nope").status_code == 404


def test_search_ranks_the_concept(client):
    hits = client.get("/api/search", params={"q": "chain rule"}).json()
    assert hits[0]["slug"] == "chain-rule"
    assert hits[0]["score"] > 0
    assert hits[0]["section"] == "academic/calc"


def test_meta_reports_sections(client):
    meta = client.get("/api/meta").json()
    # Sections come from pages *and* directories, so the seeded academic branch
    # shows up even before anything is filed in it.
    assert meta["sections"] == ["academic", "academic/calc"]
    assert meta["default_section"] == ""


def test_create_section_scaffolds_dirs(client, vault):
    r = client.post("/api/sections", json={"name": "Linear Algebra", "parent": "academic"})
    assert r.status_code == 200
    # Case is preserved now: "Linear Algebra" -> "Linear-Algebra".
    assert r.json()["section"] == "academic/Linear-Algebra"
    assert (vault.concepts_dir / "academic" / "Linear-Algebra").is_dir()
    assert (vault.source_pages_dir / "academic" / "Linear-Algebra").is_dir()
    # The new course is now visible in the section list.
    assert "academic/Linear-Algebra" in client.get("/api/meta").json()["sections"]


def test_create_section_preserves_case(client, vault):
    r = client.post("/api/sections", json={"name": "example-course ", "parent": "academic"})
    assert r.status_code == 200
    assert r.json()["section"] == "academic/example-course"
    assert (vault.concepts_dir / "academic" / "example-course").is_dir()
    assert (vault.source_pages_dir / "academic" / "example-course").is_dir()


def test_create_section_keeps_unicode(client, vault):
    r = client.post("/api/sections", json={"name": "线性代数", "parent": "academic"})
    assert r.status_code == 200
    assert r.json()["section"] == "academic/线性代数"
    assert (vault.concepts_dir / "academic" / "线性代数").is_dir()
    assert "academic/线性代数" in client.get("/api/meta").json()["sections"]


def test_create_section_rejects_duplicate_and_blank(client):
    assert client.post("/api/sections", json={"name": "Calc", "parent": "academic"}).status_code == 409
    # Case-insensitive: "calc" collides with the seeded academic/calc.
    assert client.post("/api/sections", json={"name": "CALC", "parent": "academic"}).status_code == 409
    assert client.post("/api/sections", json={"name": "   ", "parent": "academic"}).status_code == 422


def test_create_top_level_branch_at_general_root(client, vault):
    # A top-level branch (parent="" → the General root) is creatable from the web
    # UI, appears beside the seeded Academic branch, and — unlike Academic — is
    # deletable (not protected).
    r = client.post("/api/sections", json={"name": "Personal", "parent": ""})
    assert r.status_code == 200
    assert r.json()["section"] == "Personal"
    assert (vault.concepts_dir / "Personal").is_dir()
    assert (vault.source_pages_dir / "Personal").is_dir()
    assert "Personal" in client.get("/api/meta").json()["sections"]
    assert client.delete("/api/sections/Personal").status_code == 200
    assert "Personal" not in client.get("/api/meta").json()["sections"]


def test_delete_section_removes_dirs(client, vault):
    client.post("/api/sections", json={"name": "example-course", "parent": "academic"})
    r = client.delete("/api/sections/academic/example-course")
    assert r.status_code == 200
    assert r.json()["section"] == "academic/example-course"
    assert not (vault.concepts_dir / "academic" / "example-course").exists()
    assert not (vault.source_pages_dir / "academic" / "example-course").exists()
    assert "academic/example-course" not in client.get("/api/meta").json()["sections"]


def test_delete_section_wipes_ledger_cache_raw_and_overrides(client, vault):
    # Deleting a section must leave nothing behind: not just the pages, but the
    # ledger record, its normalized cache + raw bytes, and per-section overrides.
    section = "academic/example-course"
    client.post("/api/sections", json={"name": "example-course", "parent": "academic"})

    write_page(
        concept_path(vault, section, "Open Sets"),
        {"title": "Open Sets", "type": "concept", "section": section, "sources": ["course-source"]},
        "An open set is...\n",
    )
    checksum = "deadbeef"
    raw_ref = "raw/sources/course-source.pdf"
    ensure_dir(vault.normalized_dir)
    (vault.normalized_dir / f"{checksum}.md").write_text("normalized\n", "utf-8")
    ensure_dir((vault.root / raw_ref).parent)
    (vault.root / raw_ref).write_text("%PDF fake\n", "utf-8")
    state = load_state(vault)
    set_source_record(
        state, raw_ref, {"checksum": checksum, "section": section, "raw_ref": raw_ref}
    )
    save_state(vault, state)
    override = vault.section_overrides_dir / "academic" / "example-course" / "purpose.md"
    ensure_dir(override.parent)
    override.write_text("course-specific purpose\n", "utf-8")

    assert client.delete(f"/api/sections/{section}").status_code == 200

    assert not (vault.concepts_dir / "academic" / "example-course").exists()
    assert not (vault.normalized_dir / f"{checksum}.md").exists()
    assert not (vault.root / raw_ref).exists()
    assert not (vault.section_overrides_dir / "academic" / "example-course").exists()
    assert load_state(vault).get("sources", {}) == {}


def test_delete_section_keeps_other_sections_intact(client, vault):
    # A sibling section's ledger record and bytes must survive the delete.
    client.post("/api/sections", json={"name": "example-course", "parent": "academic"})
    keep_checksum = "cafef00d"
    keep_ref = "raw/sources/keep.pdf"
    ensure_dir(vault.normalized_dir)
    (vault.normalized_dir / f"{keep_checksum}.md").write_text("keep\n", "utf-8")
    state = load_state(vault)
    set_source_record(
        state,
        keep_ref,
        {"checksum": keep_checksum, "section": "academic/calc", "raw_ref": keep_ref},
    )
    save_state(vault, state)

    assert client.delete("/api/sections/academic/example-course").status_code == 200

    assert (vault.normalized_dir / f"{keep_checksum}.md").exists()
    assert keep_ref in load_state(vault).get("sources", {})


def test_delete_section_purges_vector_index(client, vault):
    # The deleted concepts' chunks must leave the vector index too, or semantic
    # search would still surface a page that no longer exists on disk.
    pytest.importorskip("lancedb")
    from llmwiki.indexing import reindex_all
    from llmwiki.vectorindex import open_index

    from tests.fakes import FakeEmbedder

    client.post("/api/sections", json={"name": "example-course", "parent": "academic"})
    write_page(
        concept_path(vault, "academic/example-course", "Open Sets"),
        {"title": "Open Sets", "type": "concept", "section": "academic/example-course", "sources": ["course-source"]},
        "Open sets, limits and continuity in topology.\n",
    )
    reindex_all(vault, FakeEmbedder())

    def stored_slugs():
        ids = open_index(vault).existing_hashes(vault.embed_model)
        return {cid.split("#", 1)[0] for cid in ids}

    assert "open-sets" in stored_slugs()  # indexed before delete

    assert client.delete("/api/sections/academic/example-course").status_code == 200

    assert "open-sets" not in stored_slugs()  # vectors dropped with the page


def test_delete_section_protects_roots(client, vault):
    assert client.delete("/api/sections/academic").status_code == 403
    assert (vault.concepts_dir / "academic").is_dir()


def test_delete_section_missing_returns_404(client):
    assert client.delete("/api/sections/academic/nope").status_code == 404


def test_search_section_scope(client):
    # The Academic branch sees the course page; a sibling section does not.
    assert client.get("/api/search", params={"q": "chain rule", "section": "academic"}).json()
    assert client.get("/api/search", params={"q": "chain rule", "section": "personal"}).json() == []


def test_overrides_list_reports_status_and_general(client):
    data = client.get("/api/overrides").json()
    assert set(data["components"]) == {
        "ingest_analysis", "ingest_generation", "answer", "lint", "purpose", "schema"
    }
    assert "knowledge base" in data["general"]["answer"]  # the general default text
    by_section = {s["section"]: s for s in data["sections"]}
    assert "academic/calc" in by_section
    assert set(by_section["academic/calc"]["status"].values()) == {"general"}


def test_overrides_set_get_and_reset(client):
    r = client.post("/api/overrides", json={"sections": ["academic/calc"], "set": {"answer": "CUSTOM"}})
    assert r.status_code == 200
    assert r.json()["updated"][0]["status"]["answer"] == "override"

    got = client.get("/api/overrides/academic/calc").json()
    assert got["components"]["answer"]["override"] == "CUSTOM"
    assert got["components"]["answer"]["effective"] == "CUSTOM"
    assert got["components"]["lint"]["override"] is None  # untouched components inherit

    r2 = client.post("/api/overrides", json={"sections": ["academic/calc"], "reset": ["answer"]})
    assert r2.json()["updated"][0]["status"]["answer"] == "general"
    assert client.get("/api/overrides/academic/calc").json()["components"]["answer"]["override"] is None


def test_overrides_multi_section_apply(client):
    # One edit fans out to several branches at once.
    r = client.post("/api/overrides", json={"sections": ["academic", "academic/calc"], "set": {"purpose": "P"}})
    assert r.status_code == 200
    statuses = {u["section"]: u["status"]["purpose"] for u in r.json()["updated"]}
    assert statuses == {"academic": "override", "academic/calc": "override"}


def test_overrides_unknown_section_404_and_component_422(client):
    assert client.post(
        "/api/overrides", json={"sections": ["does/not/exist"], "set": {"answer": "x"}}
    ).status_code == 404
    assert client.post(
        "/api/overrides", json={"sections": ["academic/calc"], "set": {"bogus": "x"}}
    ).status_code == 422


def test_home_returns_content(client):
    assert "content" in client.get("/api/home").json()


def test_home_is_scope_aware(client, monkeypatch):
    # Refreshing the course overview, then asking /api/home for that scope, serves
    # the section's own overview (not the global one).
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert client.post("/api/overview/refresh", json={"section": "academic/calc"}).status_code == 200
    body = client.get("/api/home", params={"section": "academic/calc"}).json()
    assert "chain rule" in body["content"].lower()


def test_overview_refresh_requires_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/api/overview/refresh", json={"section": "academic/calc"})
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_lint_flags_dangling_wikilink(client):
    issues = client.get("/api/lint").json()
    assert any("gradient" in i["message"] for i in issues)


def test_query_with_key(client, monkeypatch):
    # Default provider is OpenAI, so its key is what enables Ask.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # /api/query is multipart now (it can carry file attachments), so send form data.
    r = client.post("/api/query", data={"question": "state the chain rule"})
    assert r.status_code == 200
    assert "chain rule" in r.json()["answer"].lower()
    assert "chain-rule" in r.json()["pages_used"] or r.json()["pages_used"] == []


def test_query_surfaces_ungrounded_citations(vault, monkeypatch):
    # The /api/query contract exposes invented citations so the Ask view can warn.
    _seed(vault)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake = FakeProvider(answer_text="As shown in [[chain-rule]] and [[ghost-page]].")
    c = TestClient(create_app(vault, provider_factory=lambda cfg: fake))
    body = c.post("/api/query", data={"question": "anything"}).json()
    assert body["ungrounded"] == ["ghost-page"]
    assert "chain-rule" in body["pages_used"]


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
    fake = FakeProvider(answer_text="ok [[chain-rule]]")
    client = TestClient(create_app(vault, provider_factory=lambda cfg: fake))

    assert client.get("/api/meta").json()["api_key_env"] == "ANTHROPIC_API_KEY"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert client.post("/api/query", data={"question": "anything"}).status_code == 200


# --- ingest endpoint + Ask attachments --------------------------------------


def _ingest_provider() -> FakeProvider:
    """A fake wired with the analysis + generation passes ingest() needs."""
    analysis = SourceAnalysis(
        source_title="Chain Rule Notes",
        source_summary="Notes on the chain rule.",
        concept_titles=["Chain Rule"],
    )
    generation = GenerationResult(
        concept_pages=[ConceptDraft(title="Chain Rule", body="If $h=f\\circ g$ then $h'=f'(g)g'$.")],
        source_page=SourcePageDraft(summary="A short note.", grounds=["Chain Rule"]),
        log_entry="Ingested chain rule notes.",
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
        data={"section": "academic/calc"},
        files={"file": ("note.md", b"# Chain Rule\n\nThe chain rule.", "text/markdown")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ingested"
    assert body["section"] == "academic/calc"
    assert body["concept_slugs"] == ["chain-rule"]
    # Pages were written under the requested scope, and the file copied into raw/.
    assert read_page(concept_path(vault, "academic/calc", "Chain Rule")) is not None
    assert read_page(source_path(vault, "academic/calc", "note")) is not None
    assert (vault.sources_dir / "note.md").exists()


def test_ingest_general_scope_files_into_root(ingest_client, vault, monkeypatch):
    # The General scope is the root: a missing/empty section files into "", never
    # the configured default_section.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = ingest_client.post(
        "/api/ingest",
        files={"file": ("root-note.md", b"# Chain Rule\n\nbody", "text/markdown")},
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
            source_title="Chain Rule Notes",
            source_summary="Notes on the chain rule.",
            concept_titles=["Chain Rule"],
        ),
        generation=GenerationResult(
            concept_pages=[ConceptDraft(title="Chain Rule", body="Chain rule body.")],
            source_page=SourcePageDraft(summary="A short note.", grounds=["Chain Rule"]),
            log_entry="Ingested chain rule notes.",
        ),
    )
    app_client = TestClient(create_app(vault, provider_factory=lambda cfg: fake))
    r = app_client.post(
        "/api/ingest",
        data={"section": "academic/calc", "prompt": "focus on the proofs"},
        files={"file": ("note.md", b"# Chain Rule\n\nbody", "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert any("focus on the proofs" in u for u in seen)
    assert "guidance: focus on the proofs" in vault.log_file.read_text("utf-8")


def test_ingest_requires_api_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post(
        "/api/ingest",
        data={"section": "academic/calc"},
        files={"file": ("note.md", b"# x", "text/markdown")},
    )
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_ingest_requires_file_or_url(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert client.post("/api/ingest", data={"section": "academic/calc"}).status_code == 422


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
