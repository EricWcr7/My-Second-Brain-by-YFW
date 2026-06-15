import pytest
from fastapi.testclient import TestClient

from llmwiki.store import write_page
from llmwiki.web.app import create_app
from llmwiki.wiki import concept_path, source_path

from tests.fakes import FakeProvider


def _seed(vault):
    write_page(
        concept_path(vault, "Calc", "Chain Rule"),
        {"title": "Chain Rule", "type": "concept", "course": "Calc", "sources": ["lecture-1"]},
        "If $h = f \\circ g$ then $h'(x) = f'(g(x))\\,g'(x)$. See [[gradient]].\n",
    )
    write_page(
        source_path(vault, "Calc", "lecture-1"),
        {"title": "Lecture 1", "type": "source", "course": "Calc"},
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
