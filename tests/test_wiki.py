from llmwiki import wiki


def test_slugify():
    assert wiki.slugify("Retrieval Practice") == "retrieval-practice"
    assert wiki.slugify("  Big-O & Ω notation! ") == "big-o-notation"
    assert wiki.slugify("") == "untitled"


def test_section_slug_preserves_case_and_unicode():
    # Case is kept and non-Latin names survive — unlike slugify.
    assert wiki.section_slug("ProjectAlpha ") == "ProjectAlpha"
    assert wiki.section_slug("Learning Lab") == "Learning-Lab"
    assert wiki.section_slug("学习方法") == "学习方法"
    assert wiki.section_slug("  ") == "untitled"
    # slugify is unchanged: still lowercased / ASCII-folded.
    assert wiki.slugify("ProjectAlpha") == "projectalpha"


def test_extract_wikilinks_handles_aliases_and_headings():
    text = "See [[feedback-loop]] and [[retrieval-practice|practice]] plus [[page#Section]]."
    assert wiki.extract_wikilinks(text) == {"feedback-loop", "retrieval-practice", "page"}


def test_append_log_writes_greppable_entries(vault):
    wiki.append_log(vault, "ingest", "Learning Notes", detail="concepts: retrieval-practice")
    wiki.append_log(vault, "query", "how should I review", detail="saved [[q]]")

    text = vault.log_file.read_text("utf-8")
    headings = [ln for ln in text.splitlines() if ln.startswith("## [")]
    assert len(headings) == 2  # the seed header (# Log) is not a `## [` line
    assert "ingest | Learning Notes" in headings[0]
    assert "query | how should I review" in headings[1]
    assert "concepts: retrieval-practice" in text


def test_rebuild_index_lists_pages(vault):
    from llmwiki.store import write_page

    write_page(
        wiki.concept_path(vault, "academic/learning", "Retrieval Practice"),
        {"title": "Retrieval Practice", "type": "concept", "section": "academic/learning", "sources": ["s1"]},
        "Body [[feedback-loop]]",
    )
    wiki.rebuild_index(vault)
    index_text = vault.index_file.read_text("utf-8")
    assert "academic/learning" in index_text
    assert "[[retrieval-practice|Retrieval Practice]]" in index_text
