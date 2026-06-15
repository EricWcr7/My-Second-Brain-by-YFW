from llmwiki import wiki
from llmwiki.search import search, tokenize
from llmwiki.store import write_page


def _add_concept(vault, course, title, body):
    write_page(
        wiki.concept_path(vault, course, title),
        {"title": title, "type": "concept", "course": course, "sources": ["s1"]},
        body,
    )


def test_tokenize_drops_stopwords_and_short():
    assert "the" not in tokenize("the gradient is a vector")
    assert "gradient" in tokenize("the gradient is a vector")


def test_search_ranks_relevant_page_first(vault):
    _add_concept(vault, "Calc", "Gradient", "The gradient is the vector of partial derivatives.")
    _add_concept(vault, "Calc", "Continuity", "A function is continuous if limits agree.")
    hits = search(vault, "gradient vector partial derivatives", course="Calc")
    assert hits
    assert hits[0].ref.title == "Gradient"


def test_search_course_filter(vault):
    _add_concept(vault, "Calc", "Gradient", "gradient vector field")
    _add_concept(vault, "Stats", "Gradient Descent", "gradient based optimization")
    hits = search(vault, "gradient", course="Stats")
    assert {h.ref.course for h in hits} == {"Stats"}
