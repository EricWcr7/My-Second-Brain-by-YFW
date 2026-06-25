from llmwiki.ingest import (
    ConceptDraft,
    GenerationResult,
    SourceAnalysis,
    SourcePageDraft,
    ingest,
)
from llmwiki.overview import build_overview_input, refresh_overview
from llmwiki.store import write_page
from llmwiki.wiki import concept_path, overview_path, purge_section, section_ancestry

from tests.fakes import FakeProvider


def _concept(vault, section, title, body="Body.", tags=None):
    write_page(
        concept_path(vault, section, title),
        {
            "title": title,
            "type": "concept",
            "section": section,
            "tags": tags or [],
            "sources": ["s1"],
        },
        body,
    )


# --- path + ancestry helpers -------------------------------------------------


def test_overview_path_maps_general_and_sections(vault):
    # General reuses overview.md; every other section maps under overviews/.
    assert overview_path(vault, "") == vault.overview_file
    assert overview_path(vault, "academic") == vault.overviews_dir / "academic.md"
    assert (
        overview_path(vault, "academic/example-course")
        == vault.overviews_dir / "academic" / "example-course.md"
    )


def test_section_ancestry():
    assert section_ancestry("academic/example-course") == ["", "academic", "academic/example-course"]
    assert section_ancestry("academic") == ["", "academic"]
    assert section_ancestry("") == [""]


# --- the overview pass -------------------------------------------------------


def test_refresh_overview_writes_model_output(vault):
    _concept(vault, "academic/calc", "Chain Rule")
    provider = FakeProvider(answer_text="# Calc\n\nCovers [[chain-rule]].")

    path = refresh_overview(vault, provider, "academic/calc")

    assert path == overview_path(vault, "academic/calc")
    assert "Covers [[chain-rule]]" in path.read_text("utf-8")
    assert provider.calls == ["complete"]  # exactly one model call


def test_refresh_overview_empty_section_writes_stub_without_model_call(vault):
    provider = FakeProvider()

    path = refresh_overview(vault, provider, "academic/empty")

    assert path.exists()
    assert "No pages in this section yet" in path.read_text("utf-8")
    assert "complete" not in provider.calls  # empty section => no model call


def test_build_overview_input_scopes_to_section_and_descendants(vault):
    _concept(vault, "academic/calc", "Chain Rule")
    _concept(vault, "personal", "Cooking")

    catalog, slugs = build_overview_input(vault, "academic")

    # Only the academic subtree is in scope (prefix rule); the sibling branch isn't.
    assert "chain-rule" in slugs
    assert "cooking" not in slugs
    assert "[[chain-rule]]" in catalog


# --- triggers: ingest + delete ----------------------------------------------


def test_ingest_refreshes_section_and_ancestor_overviews(vault):
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nThe chain rule.", "utf-8")
    provider = FakeProvider(
        analysis=SourceAnalysis(
            source_title="N", source_summary="s", concept_titles=["Chain Rule"]
        ),
        generation=GenerationResult(
            concept_pages=[ConceptDraft(title="Chain Rule", body="body")],
            source_page=SourcePageDraft(summary="sum", grounds=["Chain Rule"]),
        ),
    )

    ingest(vault, provider, str(src), section="academic/calc")

    # The ingested section AND every ancestor up to General are refreshed.
    assert "Fake answer" in overview_path(vault, "academic/calc").read_text("utf-8")
    assert "Fake answer" in overview_path(vault, "academic").read_text("utf-8")
    assert "Fake answer" in vault.overview_file.read_text("utf-8")  # General
    assert provider.calls.count("complete") == 3


def test_purge_section_removes_own_and_descendant_overviews(vault):
    section = "academic/topo"
    _concept(vault, section, "Open Sets")
    _concept(vault, section + "/sub", "Basis")
    own = overview_path(vault, section)  # overviews/academic/topo.md
    desc = overview_path(vault, section + "/sub")  # overviews/academic/topo/sub.md
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_text("# overview\n", "utf-8")
    desc.parent.mkdir(parents=True, exist_ok=True)
    desc.write_text("# sub overview\n", "utf-8")
    assert own.exists() and desc.exists()

    purge_section(vault, section)

    assert not own.exists()  # the section's own overview file
    assert not desc.exists()  # and the descendants' overview subtree
