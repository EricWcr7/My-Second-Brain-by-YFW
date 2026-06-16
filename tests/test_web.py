import pytest
from fastapi.testclient import TestClient

from llmwiki.store import write_page
from llmwiki.web.app import create_app
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
    # Sections come from pages *and* directories, so the seeded academic/
    # non-academic branches show up even before anything is filed in them.
    assert meta["sections"] == ["academic", "academic/calc", "non-academic"]
    assert meta["default_section"] == "non-academic"


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


def test_delete_section_removes_dirs(client, vault):
    client.post("/api/sections", json={"name": "example-course", "parent": "academic"})
    r = client.delete("/api/sections/academic/example-course")
    assert r.status_code == 200
    assert r.json()["section"] == "academic/example-course"
    assert not (vault.concepts_dir / "academic" / "example-course").exists()
    assert not (vault.source_pages_dir / "academic" / "example-course").exists()
    assert "academic/example-course" not in client.get("/api/meta").json()["sections"]


def test_delete_section_protects_roots(client, vault):
    assert client.delete("/api/sections/academic").status_code == 403
    assert (vault.concepts_dir / "academic").is_dir()


def test_delete_section_missing_returns_404(client):
    assert client.delete("/api/sections/academic/nope").status_code == 404


def test_search_section_scope(client):
    # The Academic branch sees the course page; a sibling section does not.
    assert client.get("/api/search", params={"q": "chain rule", "section": "academic"}).json()
    assert client.get("/api/search", params={"q": "chain rule", "section": "non-academic"}).json() == []


def test_home_returns_content(client):
    assert "content" in client.get("/api/home").json()


def test_lint_flags_dangling_wikilink(client):
    issues = client.get("/api/lint").json()
    assert any("gradient" in i["message"] for i in issues)


def test_query_with_key(client, monkeypatch):
    # Default provider is OpenAI, so its key is what enables Ask.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = client.post("/api/query", json={"question": "state the chain rule"})
    assert r.status_code == 200
    assert "chain rule" in r.json()["answer"].lower()
    assert "chain-rule" in r.json()["pages_used"] or r.json()["pages_used"] == []


def test_query_without_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/api/query", json={"question": "anything"})
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
    assert client.post("/api/query", json={"question": "anything"}).status_code == 200
