from llmwiki.ingest import (
    ConceptDraft,
    GenerationResult,
    SourceAnalysis,
    SourcePageDraft,
    ingest,
)
from llmwiki.store import read_page
from llmwiki.wiki import concept_path, source_path

from tests.fakes import FakeProvider


def _provider():
    analysis = SourceAnalysis(
        source_title="Chain Rule Notes",
        source_summary="Notes on the chain rule.",
        concept_titles=["Chain Rule"],
    )
    generation = GenerationResult(
        concept_pages=[
            ConceptDraft(
                title="Chain Rule",
                tags=["derivatives"],
                body="## Definition\n\nIf $h=f\\circ g$ then $h'=f'(g)\\,g'$.\n\n"
                "## Related\n\nbuilds on [[derivative]].",
            )
        ],
        source_page=SourcePageDraft(summary="A short note.", grounds=["Chain Rule"]),
        log_entry="Ingested chain rule notes.",
    )
    return FakeProvider(analysis=analysis, generation=generation)


def test_ingest_creates_pages_and_provenance(vault):
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nThe chain rule differentiates compositions.", "utf-8")

    provider = _provider()
    result = ingest(vault, provider, str(src), course="Calc")

    assert result.status == "ingested"
    assert result.source_slug == "note"
    assert result.concept_slugs == ["chain-rule"]

    concept = read_page(concept_path(vault, "Calc", "Chain Rule"))
    assert concept is not None
    assert concept.metadata["type"] == "concept"
    assert "note" in concept.metadata["sources"]  # provenance back to the source

    source = read_page(source_path(vault, "Calc", "note"))
    assert source is not None
    assert source.metadata["type"] == "source"
    assert source.metadata["path"] == "raw/sources/note.md"

    assert "chain-rule" in vault.index_file.read_text("utf-8")


def test_ingest_skips_unchanged_source(vault):
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nUnchanged content.", "utf-8")

    first = ingest(vault, _provider(), str(src), course="Calc")
    assert first.status == "ingested"

    second = ingest(vault, _provider(), str(src), course="Calc")
    assert second.status == "skipped"
    assert second.reason == "unchanged"


def test_ingest_copies_external_file_into_raw(vault, tmp_path):
    external = tmp_path.parent / "external_note.md"
    external.write_text("# Topic\n\nbody", "utf-8")

    ingest(vault, _provider(), str(external), course="Calc")
    copied = vault.sources_dir / "external_note.md"
    assert copied.exists()
