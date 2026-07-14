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
        overview_path(vault, "academic/LearningLab")
        == vault.overviews_dir / "academic" / "LearningLab.md"
    )


def test_section_ancestry():
    assert section_ancestry("academic/LearningLab") == ["", "academic", "academic/LearningLab"]
    assert section_ancestry("academic") == ["", "academic"]
    assert section_ancestry("") == [""]


# --- the overview pass -------------------------------------------------------


def test_refresh_overview_writes_model_output(vault):
    _concept(vault, "academic/learning", "Retrieval Practice")
    provider = FakeProvider(answer_text="# Learning\n\nCovers [[retrieval-practice]].")

    path = refresh_overview(vault, provider, "academic/learning")

    assert path == overview_path(vault, "academic/learning")
    assert "Covers [[retrieval-practice]]" in path.read_text("utf-8")
    assert provider.calls == ["complete"]  # exactly one model call


def test_refresh_overview_empty_section_writes_stub_without_model_call(vault):
    provider = FakeProvider()

    path = refresh_overview(vault, provider, "academic/empty")

    assert path.exists()
    assert "No pages in this section yet" in path.read_text("utf-8")
    assert "complete" not in provider.calls  # empty section => no model call


def test_build_overview_input_scopes_to_section_and_descendants(vault):
    _concept(vault, "academic/learning", "Retrieval Practice")
    _concept(vault, "projects", "Launch Checklist")

    catalog, slugs = build_overview_input(vault, "academic")

    # Only the academic subtree is in scope (prefix rule); the sibling branch isn't.
    assert "retrieval-practice" in slugs
    assert "launch-checklist" not in slugs
    assert "[[retrieval-practice]]" in catalog


# --- triggers: ingest + delete ----------------------------------------------


def test_ingest_refreshes_section_and_ancestor_overviews(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nRecall strengthens memory.", "utf-8")
    provider = FakeProvider(
        analysis=SourceAnalysis(
            source_title="N", source_summary="s", concept_titles=["Retrieval Practice"]
        ),
        generation=GenerationResult(
            concept_pages=[ConceptDraft(title="Retrieval Practice", body="body")],
            source_page=SourcePageDraft(summary="sum", grounds=["Retrieval Practice"]),
        ),
    )

    ingest(vault, provider, str(src), section="academic/learning")

    # The ingested section AND every ancestor up to General are refreshed.
    assert "Fake answer" in overview_path(vault, "academic/learning").read_text("utf-8")
    assert "Fake answer" in overview_path(vault, "academic").read_text("utf-8")
    assert "Fake answer" in vault.overview_file.read_text("utf-8")  # General
    assert provider.calls.count("complete") == 3


def test_purge_section_removes_own_and_descendant_overviews(vault):
    section = "projects/learning"
    _concept(vault, section, "Review Schedule")
    _concept(vault, section + "/sub", "Weekly Check-in")
    own = overview_path(vault, section)
    desc = overview_path(vault, section + "/sub")
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_text("# overview\n", "utf-8")
    desc.parent.mkdir(parents=True, exist_ok=True)
    desc.write_text("# sub overview\n", "utf-8")
    assert own.exists() and desc.exists()

    purge_section(vault, section)

    assert not own.exists()  # the section's own overview file
    assert not desc.exists()  # and the descendants' overview subtree
