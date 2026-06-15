from llmwiki import wiki
from llmwiki.search import search, tokenize
from llmwiki.store import write_page
from llmwiki.wiki import section_contains


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
    assert not section_contains("non-academic", "academic/calc")
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
    _add_concept(vault, "non-academic", "Gradient Sky", "the gradient of the sunset sky")

    # A course sees only itself.
    calc = search(vault, "gradient", section="academic/calc")
    assert {h.ref.section for h in calc} == {"academic/calc"}

    # The Academic branch sees every course, but not the non-academic sibling.
    academic = search(vault, "gradient", section="academic")
    assert {h.ref.section for h in academic} == {"academic/calc", "academic/stats"}

    # General (no scope) sees the whole knowledge base.
    everything = search(vault, "gradient")
    assert {h.ref.section for h in everything} == {
        "academic/calc",
        "academic/stats",
        "non-academic",
    }
