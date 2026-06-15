from llmwiki.query import answer
from llmwiki.store import write_page
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
