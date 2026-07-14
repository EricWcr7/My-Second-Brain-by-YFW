from llmwiki.lint import LintFindings, lint
from llmwiki.store import write_page
from llmwiki.wiki import concept_path, source_path

from tests.fakes import FakeProvider


def test_lint_flags_structural_problems(vault):
    # A real source page so valid provenance can resolve.
    write_page(
        source_path(vault, "projects/learning", "handbook"),
        {"title": "Learning Handbook", "type": "source", "section": "projects/learning", "kind": "markdown",
         "path": "raw/sources/handbook.md"},
        "summary",
    )
    # Concept with a dangling link and a bad source reference.
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["ghost"]},
        "See [[nowhere]] for details.",
    )
    # Concept missing provenance entirely.
    write_page(
        concept_path(vault, "projects/learning", "Spaced Repetition"),
        {"title": "Spaced Repetition", "type": "concept", "section": "projects/learning", "sources": []},
        "Body.",
    )

    issues = lint(vault, section="projects/learning")
    messages = [(i.level, i.message) for i in issues]

    assert any(lvl == "error" and "no `sources`" in msg for lvl, msg in messages)
    assert any("dangling wikilink [[nowhere]]" in msg for _, msg in messages)
    assert any("'ghost' has no matching source page" in msg for _, msg in messages)


def test_lint_clean_wiki_has_no_errors(vault):
    write_page(
        source_path(vault, "projects/learning", "handbook"),
        {"title": "Learning Handbook", "type": "source", "section": "projects/learning", "kind": "markdown",
         "path": "raw/sources/handbook.md"},
        "summary mentions [[retrieval-practice]]",
    )
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["handbook"]},
        "Retrieval practice. Related: [[retrieval-practice]] self-ref aside.",
    )
    issues = lint(vault, section="projects/learning")
    assert not any(i.level == "error" for i in issues)


def test_deep_lint_surfaces_suggestion_categories(vault):
    write_page(
        concept_path(vault, "projects/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "projects/learning", "sources": ["s1"]},
        "retrieval practice body",
    )
    findings = LintFindings(
        missing_cross_references=["[[retrieval-practice]] should link [[spaced-repetition]]"],
        new_questions=["How does retrieval practice support long-term recall?"],
        sources_to_seek=["A research review on learning methods"],
        data_gaps=["A practical weekly review example"],
    )
    provider = FakeProvider(findings=findings)

    issues = lint(vault, provider=provider, deep=True, section="projects/learning")
    messages = [i.message for i in issues]

    assert any("missing cross-reference:" in m for m in messages)
    assert any("question to investigate:" in m for m in messages)
    assert any("source to seek:" in m for m in messages)
    assert any("data gap (web search):" in m for m in messages)
