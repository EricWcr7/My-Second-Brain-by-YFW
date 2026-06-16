from llmwiki import wiki


def test_slugify():
    assert wiki.slugify("Lagrange Multipliers") == "lagrange-multipliers"
    assert wiki.slugify("  Big-O & Ω notation! ") == "big-o-notation"
    assert wiki.slugify("") == "untitled"


def test_section_slug_preserves_case_and_unicode():
    # Case is kept (course codes) and non-Latin names survive — unlike slugify.
    assert wiki.section_slug("example-course ") == "example-course"
    assert wiki.section_slug("Linear Algebra") == "Linear-Algebra"
    assert wiki.section_slug("线性代数") == "线性代数"
    assert wiki.section_slug("  ") == "untitled"
    # slugify is unchanged: still lowercased / ASCII-folded.
    assert wiki.slugify("example-course") == "example-course"


def test_extract_wikilinks_handles_aliases_and_headings():
    text = "See [[gradient]] and [[chain-rule|the Chain Rule]] plus [[page#Section]]."
    assert wiki.extract_wikilinks(text) == {"gradient", "chain-rule", "page"}


def test_append_log_writes_greppable_entries(vault):
    wiki.append_log(vault, "ingest", "Chain Rule Notes", detail="concepts: chain-rule")
    wiki.append_log(vault, "query", "what is the gradient", detail="saved [[q]]")

    text = vault.log_file.read_text("utf-8")
    headings = [ln for ln in text.splitlines() if ln.startswith("## [")]
    assert len(headings) == 2  # the seed header (# Log) is not a `## [` line
    assert "ingest | Chain Rule Notes" in headings[0]
    assert "query | what is the gradient" in headings[1]
    assert "concepts: chain-rule" in text


def test_rebuild_index_lists_pages(vault):
    from llmwiki.store import write_page

    write_page(
        wiki.concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "Body [[divergence]]",
    )
    wiki.rebuild_index(vault)
    index_text = vault.index_file.read_text("utf-8")
    assert "academic/calc" in index_text
    assert "[[gradient|Gradient]]" in index_text
