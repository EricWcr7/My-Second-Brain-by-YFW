from llmwiki.query import _format_directive, answer
from llmwiki.store import read_page, write_page
from llmwiki.wiki import concept_path

from tests.fakes import FakeProvider


def test_answer_uses_retrieved_pages(vault):
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "The gradient is the vector of partial derivatives.",
    )
    provider = FakeProvider(answer_text="The gradient points uphill. [[gradient]]")
    result = answer(vault, provider, "what is the gradient", section="academic/calc")

    assert "gradient" in result.answer.lower()
    assert "gradient" in result.pages_used
    assert "complete" in provider.calls


def test_answer_flags_invented_citation(vault):
    # The model cites a real page ([[gradient]]) and invents one ([[made-up-page]]).
    # The grounding check must surface the invented one and keep it out of pages_used.
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "The gradient is the vector of partial derivatives.",
    )
    provider = FakeProvider(answer_text="See [[gradient]] and also [[made-up-page]].")
    result = answer(vault, provider, "what is the gradient", section="academic/calc")

    assert result.ungrounded == ["made-up-page"]
    assert "gradient" in result.pages_used
    assert "made-up-page" not in result.pages_used


def test_answer_grounded_citation_not_flagged(vault):
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "The gradient is the vector of partial derivatives.",
    )
    provider = FakeProvider(answer_text="The gradient points uphill. [[gradient]]")
    result = answer(vault, provider, "what is the gradient", section="academic/calc")

    assert result.ungrounded == []
    assert result.pages_used == ["gradient"]


def test_answer_save_writes_query_page(vault):
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "gradient content",
    )
    provider = FakeProvider(answer_text="answer body")
    result = answer(vault, provider, "explain gradient", section="academic/calc", save=True)
    assert result.saved_path is not None
    assert result.saved_path.exists()


def test_format_directive_is_format_specific():
    assert _format_directive("prose") == ""
    assert "table" in _format_directive("table").lower()
    assert "marp" in _format_directive("slides").lower()


def test_answer_slides_save_sets_marp_frontmatter(vault):
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "gradient content",
    )
    provider = FakeProvider(answer_text="# Title\n\n---\n\nslide body")
    result = answer(
        vault, provider, "explain gradient", section="academic/calc", save=True, fmt="slides"
    )
    assert result.saved_path is not None
    saved = read_page(result.saved_path)
    assert saved.metadata.get("marp") is True
