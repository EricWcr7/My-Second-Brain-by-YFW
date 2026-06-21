"""Unit tests for the pure chunking layer (no LLM, no LanceDB)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.chunking import chunk_page
from llmwiki.wiki import PageRef


def _ref() -> PageRef:
    return PageRef(
        slug="gradient",
        title="Gradient",
        section="academic/calc",
        page_type="concept",
        path=Path("x.md"),
    )


def test_splits_on_headings_with_lede():
    content = (
        "Intro lede before any heading.\n\n"
        "## Definition\nThe gradient is a vector.\n\n"
        "## Properties\nPoints toward steepest ascent.\n"
    )
    chunks = chunk_page(_ref(), content, max_chars=1500)
    assert [c.heading for c in chunks] == ["", "Definition", "Properties"]
    assert [c.id for c in chunks] == ["gradient#0", "gradient#1", "gradient#2"]
    # Every chunk carries page identity for citation aggregation.
    assert all(c.page_slug == "gradient" and c.section == "academic/calc" for c in chunks)


def test_content_hash_changes_with_text():
    a = chunk_page(_ref(), "## H\none", max_chars=1500)[0]
    b = chunk_page(_ref(), "## H\ntwo", max_chars=1500)[0]
    assert a.content_hash != b.content_hash


def test_long_section_is_subsplit():
    body = "## Big\n" + "\n\n".join(f"Paragraph number {i} with words." for i in range(40))
    chunks = chunk_page(_ref(), body, max_chars=200)
    assert len(chunks) > 1
    assert all(c.heading == "Big" for c in chunks)


def test_display_math_is_not_split():
    # A $$...$$ block has no internal blank line, and packing holds a flush until
    # the fences are balanced — so the block always lands inside a single chunk.
    body = "## Math\n" + "x " * 200 + "\n\n$$\na = b + c\n$$\n\n" + "y " * 200
    chunks = chunk_page(_ref(), body, max_chars=150)
    holders = [c for c in chunks if "$$" in c.text]
    assert len(holders) == 1
    assert holders[0].text.count("$$") == 2  # both fences together
