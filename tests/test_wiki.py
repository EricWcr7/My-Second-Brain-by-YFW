from llmwiki import wiki


def test_slugify():
    assert wiki.slugify("Lagrange Multipliers") == "lagrange-multipliers"
    assert wiki.slugify("  Big-O & Ω notation! ") == "big-o-notation"
    assert wiki.slugify("") == "untitled"


def test_extract_wikilinks_handles_aliases_and_headings():
    text = "See [[gradient]] and [[chain-rule|the Chain Rule]] plus [[page#Section]]."
    assert wiki.extract_wikilinks(text) == {"gradient", "chain-rule", "page"}


def test_rebuild_index_lists_pages(vault):
    from llmwiki.store import write_page

    write_page(
        wiki.concept_path(vault, "Calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "course": "Calc", "sources": ["s1"]},
        "Body [[divergence]]",
    )
    wiki.rebuild_index(vault)
    index_text = vault.index_file.read_text("utf-8")
    assert "## Calc" in index_text
    assert "[[gradient|Gradient]]" in index_text
