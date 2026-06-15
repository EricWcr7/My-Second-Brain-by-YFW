from llmwiki.lint import LintFindings, lint
from llmwiki.store import write_page
from llmwiki.wiki import concept_path, source_path

from tests.fakes import FakeProvider


def test_lint_flags_structural_problems(vault):
    # A real source page so valid provenance can resolve.
    write_page(
        source_path(vault, "academic/calc", "lecture1"),
        {"title": "Lecture 1", "type": "source", "section": "academic/calc", "kind": "pdf",
         "path": "raw/sources/lecture1.pdf"},
        "summary",
    )
    # Concept with a dangling link and a bad source reference.
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["ghost"]},
        "See [[nowhere]] for details.",
    )
    # Concept missing provenance entirely.
    write_page(
        concept_path(vault, "academic/calc", "Divergence"),
        {"title": "Divergence", "type": "concept", "section": "academic/calc", "sources": []},
        "Body.",
    )

    issues = lint(vault, section="academic/calc")
    messages = [(i.level, i.message) for i in issues]

    assert any(lvl == "error" and "no `sources`" in msg for lvl, msg in messages)
    assert any("dangling wikilink [[nowhere]]" in msg for _, msg in messages)
    assert any("'ghost' has no matching source page" in msg for _, msg in messages)


def test_lint_clean_wiki_has_no_errors(vault):
    write_page(
        source_path(vault, "academic/calc", "lecture1"),
        {"title": "Lecture 1", "type": "source", "section": "academic/calc", "kind": "pdf",
         "path": "raw/sources/lecture1.pdf"},
        "summary mentions [[gradient]]",
    )
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["lecture1"]},
        "The gradient. Related: [[gradient]] self-ref aside.",
    )
    issues = lint(vault, section="academic/calc")
    assert not any(i.level == "error" for i in issues)


def test_deep_lint_surfaces_suggestion_categories(vault):
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "gradient body",
    )
    findings = LintFindings(
        missing_cross_references=["[[gradient]] should link [[divergence]]"],
        new_questions=["How does the gradient relate to the curl?"],
        sources_to_seek=["A vector-calculus textbook chapter"],
        data_gaps=["A numerical gradient-descent example"],
    )
    provider = FakeProvider(findings=findings)

    issues = lint(vault, provider=provider, deep=True, section="academic/calc")
    messages = [i.message for i in issues]

    assert any("missing cross-reference:" in m for m in messages)
    assert any("question to investigate:" in m for m in messages)
    assert any("source to seek:" in m for m in messages)
    assert any("data gap (web search):" in m for m in messages)
