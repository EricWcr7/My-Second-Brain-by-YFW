import json

import pytest

from llmwiki.chunking import segment_markdown
from llmwiki.ingest import (
    ConceptDraft,
    GenerationResult,
    SourceAnalysis,
    SourcePageDraft,
    ingest,
)
from llmwiki.providers import ProviderError
from llmwiki.store import read_page
from llmwiki.wiki import concept_path, source_path

from tests.fakes import FakeProvider


def _provider():
    analysis = SourceAnalysis(
        source_title="Learning Notes",
        source_summary="Notes on retrieval practice.",
        concept_titles=["Retrieval Practice"],
    )
    generation = GenerationResult(
        concept_pages=[
            ConceptDraft(
                title="Retrieval Practice",
                tags=["learning"],
                body="## Practice\n\nRecall an idea before checking the source.\n\n"
                "## Related\n\nbuilds on [[feedback-loop]].",
            )
        ],
        source_page=SourcePageDraft(summary="A short note.", grounds=["Retrieval Practice"]),
        log_entry="Ingested retrieval practice notes.",
    )
    return FakeProvider(analysis=analysis, generation=generation)


def test_ingest_creates_pages_and_provenance(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nRetrieval practice strengthens long-term recall.", "utf-8")

    provider = _provider()
    result = ingest(vault, provider, str(src), section="academic/learning")

    assert result.status == "ingested"
    assert result.source_slug == "note"
    assert result.concept_slugs == ["retrieval-practice"]

    concept = read_page(concept_path(vault, "academic/learning", "Retrieval Practice"))
    assert concept is not None
    assert concept.metadata["type"] == "concept"
    assert concept.metadata["section"] == "academic/learning"
    assert "note" in concept.metadata["sources"]  # provenance back to the source

    source = read_page(source_path(vault, "academic/learning", "note"))
    assert source is not None
    assert source.metadata["type"] == "source"
    assert source.metadata["path"] == "raw/sources/note.md"

    assert "retrieval-practice" in vault.index_file.read_text("utf-8")

    # The operation is journaled as a greppable log entry.
    log_text = vault.log_file.read_text("utf-8")
    assert any(line.startswith("## [") and "ingest |" in line for line in log_text.splitlines())
    assert "Ingested retrieval practice notes." in log_text  # gen.log_entry becomes the detail line


def test_ingest_normalizes_the_section_argument(vault):
    # The web UI sends canonical sections, but the CLI can pass raw text. ingest()
    # canonicalizes once up front, so placement and frontmatter use the normalized
    # form (iter_pages normalizes on read — a raw string would diverge from disk).
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nbody", "utf-8")

    result = ingest(vault, _provider(), str(src), section="academic//learning notes/")
    assert result.status == "ingested"

    concept = read_page(concept_path(vault, "academic/learning-notes", "Retrieval Practice"))
    assert concept is not None
    assert concept.metadata["section"] == "academic/learning-notes"

    source = read_page(source_path(vault, "academic/learning-notes", "note"))
    assert source is not None
    assert source.metadata["section"] == "academic/learning-notes"


def test_ingest_skips_unchanged_source(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")

    first = ingest(vault, _provider(), str(src), section="academic/learning")
    assert first.status == "ingested"

    provider = _provider()
    second = ingest(vault, provider, str(src), section="academic/learning")
    assert second.status == "skipped"
    assert second.reason == "unchanged"
    # The duplicate check runs before any model pass — no compile calls.
    assert not any(c.startswith("parse:") for c in provider.calls)


def test_ingest_reingests_when_concept_page_deleted(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    concept_path(vault, "academic/learning", "Retrieval Practice").unlink()

    again = ingest(vault, _provider(), str(src), section="academic/learning")
    assert again.status == "ingested"
    assert concept_path(vault, "academic/learning", "Retrieval Practice").exists()


def test_ingest_reingests_when_source_page_deleted(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    source_path(vault, "academic/learning", "note").unlink()

    again = ingest(vault, _provider(), str(src), section="academic/learning")
    assert again.status == "ingested"
    assert source_path(vault, "academic/learning", "note").exists()


def test_ingest_skips_duplicate_content_under_new_filename(vault, tmp_path):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nSame bytes.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    copy = tmp_path.parent / "note (1).md"
    copy.write_text("# Retrieval Practice\n\nSame bytes.", "utf-8")

    result = ingest(vault, _provider(), str(copy), section="academic/learning")
    assert result.status == "skipped"
    assert result.reason == "duplicate"
    assert result.source_key == "raw/sources/note.md"
    assert result.source_slug == "note"
    # The rejected copy never lands in raw/ and the ledger keeps one record.
    assert not list(vault.sources_dir.glob("note (1)*"))
    state = json.loads(vault.state_file.read_text("utf-8"))
    assert list(state["sources"]) == ["raw/sources/note.md"]


def test_ingest_same_content_different_section_proceeds(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    result = ingest(vault, _provider(), str(src), section="academic/other")
    assert result.status == "ingested"
    # The single per-key record follows the latest ingest...
    state = json.loads(vault.state_file.read_text("utf-8"))
    assert state["sources"]["raw/sources/note.md"]["section"] == "academic/other"
    # ...while the earlier section's pages stay on disk.
    assert source_path(vault, "academic/learning", "note").exists()
    assert concept_path(vault, "academic/learning", "Retrieval Practice").exists()


def test_ingest_user_prompt_forces_reingest(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    provider = _provider()
    result = ingest(
        vault, provider, str(src), section="academic/learning", user_prompt="reshape the pages"
    )
    assert result.status == "ingested"
    assert any(c.startswith("parse:") for c in provider.calls)


def test_ingest_force_bypasses_intact_skip(vault):
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    result = ingest(vault, _provider(), str(src), section="academic/learning", force=True)
    assert result.status == "ingested"


def test_ingest_file_skip_avoids_provider_calls(vault, tmp_path):
    # For file sources the duplicate check runs before load_source, so a skipped
    # re-upload of an image never pays for vision transcription.
    img = tmp_path.parent / "dedup-diagram.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake png bytes")
    analysis = SourceAnalysis(
        source_title="Diagram", source_summary="A diagram.", concept_titles=["Diagram Concept"]
    )
    generation = GenerationResult(
        concept_pages=[ConceptDraft(title="Diagram Concept", body="From the diagram.")],
        source_page=SourcePageDraft(summary="An image source.", grounds=["Diagram Concept"]),
    )
    ingest(
        vault,
        FakeProvider(analysis=analysis, generation=generation),
        str(img),
        section="academic/learning",
    )

    fresh = FakeProvider(analysis=analysis, generation=generation)
    result = ingest(vault, fresh, str(img), section="academic/learning")
    assert result.status == "skipped"
    assert not any(c.startswith(("parse:", "transcribe")) for c in fresh.calls)
    # The skip path never loads the source; the title comes from the record.
    state = json.loads(vault.state_file.read_text("utf-8"))
    assert result.title == state["sources"]["raw/assets/dedup-diagram.png"]["title"]


def test_ingest_reingests_when_record_missing_source_slug(vault):
    # Degenerate ledger records never match; the safe direction is re-ingest.
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    state = json.loads(vault.state_file.read_text("utf-8"))
    del state["sources"]["raw/sources/note.md"]["source_slug"]
    vault.state_file.write_text(json.dumps(state), "utf-8")

    result = ingest(vault, _provider(), str(src), section="academic/learning")
    assert result.status == "ingested"


def test_ingest_skip_tolerates_missing_concept_slugs(vault):
    # Older records may lack concept_slugs; the source page alone gates the skip.
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nUnchanged content.", "utf-8")
    ingest(vault, _provider(), str(src), section="academic/learning")

    state = json.loads(vault.state_file.read_text("utf-8"))
    del state["sources"]["raw/sources/note.md"]["concept_slugs"]
    vault.state_file.write_text(json.dumps(state), "utf-8")

    result = ingest(vault, _provider(), str(src), section="academic/learning")
    assert result.status == "skipped"
    assert result.reason == "unchanged"


def test_ingest_copies_external_file_into_raw(vault, tmp_path):
    external = tmp_path.parent / "external_note.md"
    external.write_text("# Topic\n\nbody", "utf-8")

    ingest(vault, _provider(), str(external), section="academic/learning")
    copied = vault.sources_dir / "external_note.md"
    assert copied.exists()


def test_ingest_image_stores_asset_and_embeds(vault, tmp_path):
    img = tmp_path.parent / "diagram.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake png bytes")

    analysis = SourceAnalysis(
        source_title="Diagram",
        source_summary="A diagram.",
        concept_titles=["Diagram Concept"],
    )
    generation = GenerationResult(
        concept_pages=[ConceptDraft(title="Diagram Concept", body="From the diagram.")],
        source_page=SourcePageDraft(summary="An image source.", grounds=["Diagram Concept"]),
    )
    provider = FakeProvider(analysis=analysis, generation=generation)

    ingest(vault, provider, str(img), section="academic/learning")

    # Images are stored under raw/assets/, not raw/sources/.
    assert (vault.assets_dir / "diagram.png").exists()
    assert not (vault.sources_dir / "diagram.png").exists()

    source = read_page(source_path(vault, "academic/learning", "diagram"))
    assert source is not None
    assert source.metadata["kind"] == "image"
    assert source.metadata.get("assets") == ["raw/assets/diagram.png"]
    assert "![" in source.content  # the asset is embedded for viewing


class _ScriptedProvider(FakeProvider):
    """Returns queued analysis/generation results (one per parse call) and records
    each call's user prompt, so a test can assert cross-segment accumulation."""

    def __init__(self, analyses, generations):
        super().__init__()
        self._analyses = list(analyses)
        self._generations = list(generations)
        self.user_prompts: list[str] = []

    def parse(self, system, user, schema, *, model=None, max_tokens=16000):
        self.calls.append(f"parse:{schema.__name__}")
        self.user_prompts.append(user)
        if schema is SourceAnalysis:
            return self._analyses.pop(0)
        if schema is GenerationResult:
            return self._generations.pop(0)
        raise AssertionError(f"unexpected schema {schema!r}")


def test_ingest_segments_large_source_into_one_provenance(vault):
    # A source larger than the per-pass budget is compiled segment by segment and
    # merged into ONE source / provenance record, with concepts accumulating.
    vault.ingest_segment_max_tokens = 50  # ~200 chars/segment, forces a split
    page1 = "<!-- page 1 -->\n" + "Active recall is described here. " * 12
    page2 = "<!-- page 2 -->\n" + "Spaced repetition is described here. " * 12
    src = vault.root / "book.md"
    src.write_text(page1 + "\n\n" + page2, "utf-8")

    provider = _ScriptedProvider(
        analyses=[
            SourceAnalysis(source_title="Guide", source_summary="Part 1.", concept_titles=["Active Recall"]),
            SourceAnalysis(source_title="Guide", source_summary="Part 2.", concept_titles=["Spaced Repetition"]),
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Active Recall", body="Active recall body.")],
                source_page=SourcePageDraft(summary="Covers active recall.", grounds=["Active Recall"]),
            ),
            GenerationResult(
                concept_pages=[ConceptDraft(title="Spaced Repetition", body="Spaced repetition body.")],
                source_page=SourcePageDraft(summary="Covers spaced repetition.", grounds=["Spaced Repetition"]),
            ),
        ],
    )
    result = ingest(vault, provider, str(src), section="academic/learning")

    # Two segments => two analysis + two generation passes.
    assert provider.calls.count("parse:SourceAnalysis") == 2
    assert provider.calls.count("parse:GenerationResult") == 2

    # Both concepts written, under one source slug.
    assert set(result.concept_slugs) == {"active-recall", "spaced-repetition"}
    assert read_page(concept_path(vault, "academic/learning", "Active Recall")) is not None
    assert read_page(concept_path(vault, "academic/learning", "Spaced Repetition")) is not None

    # ONE provenance record for the whole source.
    sources = json.loads(vault.state_file.read_text("utf-8"))["sources"]
    assert list(sources) == ["raw/sources/book.md"]
    assert set(sources["raw/sources/book.md"]["concept_slugs"]) == {"active-recall", "spaced-repetition"}

    # ONE source page, summarizing both parts and linking both concepts.
    source = read_page(source_path(vault, "academic/learning", "book"))
    assert source is not None
    assert "Covers active recall." in source.content and "Covers spaced repetition." in source.content
    assert "[[active-recall" in source.content and "[[spaced-repetition" in source.content

    # Accumulation wiring: the 2nd segment's analysis was told "Active Recall" already
    # exists (it was written by segment 1). Call order: a1, g1, a2, g2.
    assert "Active Recall" in provider.user_prompts[2]


def _single_segment_provider() -> "_ScriptedProvider":
    return _ScriptedProvider(
        analyses=[
            SourceAnalysis(
                source_title="Learning Notes",
                source_summary="Notes on retrieval practice.",
                concept_titles=["Retrieval Practice"],
            )
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Retrieval Practice", body="Retrieval practice body.")],
                source_page=SourcePageDraft(summary="Covers retrieval practice.", grounds=["Retrieval Practice"]),
                log_entry="Ingested retrieval practice notes.",
            )
        ],
    )


def test_ingest_threads_user_prompt_into_both_passes(vault):
    # An optional user instruction rides into BOTH compile passes (analysis at
    # index 0, generation at index 1) and is journaled for provenance.
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nRetrieval practice strengthens long-term recall.", "utf-8")

    provider = _single_segment_provider()
    ingest(vault, provider, str(src), section="academic/learning", user_prompt="focus on practical examples")

    assert "User instruction" in provider.user_prompts[0]
    assert "focus on practical examples" in provider.user_prompts[0]
    assert "focus on practical examples" in provider.user_prompts[1]

    assert "guidance: focus on practical examples" in vault.log_file.read_text("utf-8")


def test_ingest_without_user_prompt_leaves_prompts_and_log_unchanged(vault):
    # The default (no guidance) path must be byte-for-byte unchanged: no
    # instruction block in the prompts and no guidance line in the log.
    src = vault.root / "note.md"
    src.write_text("# Retrieval Practice\n\nRetrieval practice strengthens long-term recall.", "utf-8")

    provider = _single_segment_provider()
    ingest(vault, provider, str(src), section="academic/learning")

    assert "User instruction" not in provider.user_prompts[0]
    assert "User instruction" not in provider.user_prompts[1]
    assert "guidance:" not in vault.log_file.read_text("utf-8")


def test_ingest_sees_existing_concepts_despite_raw_section_spelling(vault):
    # The existing-concepts context fed to the analysis pass filters pages by
    # section. iter_pages returns normalized sections, so a raw caller spelling
    # ("academic//learning") must still match concepts filed under the canonical scope.
    seed = vault.root / "note.md"
    seed.write_text("# Retrieval Practice\n\nRetrieval practice.", "utf-8")
    ingest(vault, _provider(), str(seed), section="academic/learning")

    other = vault.root / "reflection.md"
    other.write_text("# Weekly Reflection\n\nReview what worked.", "utf-8")
    provider = _ScriptedProvider(
        analyses=[
            SourceAnalysis(source_title="Reflection", source_summary="s", concept_titles=["Weekly Reflection"])
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Weekly Reflection", body="body")],
                source_page=SourcePageDraft(summary="s", grounds=["Weekly Reflection"]),
            )
        ],
    )
    ingest(vault, provider, str(other), section="academic//learning")

    # The seeded concept is visible to the analysis pass (the source text itself
    # never mentions it, so this can only come from the existing-concepts block).
    assert "Retrieval Practice" in provider.user_prompts[0]


def test_ingest_single_segment_unchanged_for_small_source(vault):
    # A source within budget still compiles in exactly one analysis + generation
    # pass (no behavior change for the common case).
    src = vault.root / "small.md"
    src.write_text("# Retrieval Practice\n\nShort note.", "utf-8")
    provider = _ScriptedProvider(
        analyses=[SourceAnalysis(source_title="N", source_summary="s", concept_titles=["Retrieval Practice"])],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Retrieval Practice", body="body")],
                source_page=SourcePageDraft(summary="one part", grounds=["Retrieval Practice"]),
            )
        ],
    )
    ingest(vault, provider, str(src), section="academic/learning")
    # One analysis + one generation pass for the single segment...
    assert provider.calls[:3] == [
        f"with_timeout:{vault.ingest_request_timeout}",
        "parse:SourceAnalysis",
        "parse:GenerationResult",
    ]
    # ...then a best-effort overview refresh for the section and its two ancestors
    # (General + academic), each a `complete` call.
    assert provider.calls.count("complete") == 3
    source = read_page(source_path(vault, "academic/learning", "small"))
    assert source is not None and "one part" in source.content
    assert "compiled in" not in source.content  # no multi-part preamble


def test_ingest_scopes_the_ingest_request_timeout(vault):
    # Ingest rescopes its provider to the longer ingest timeout before any model
    # call (so multi-segment compilation + vision transcription get the headroom),
    # leaving the interactive request_timeout untouched for query/lint.
    src = vault.root / "n.md"
    src.write_text("# Retrieval Practice\n\nShort.", "utf-8")
    provider = _provider()
    ingest(vault, provider, str(src), section="academic/learning")
    assert provider.calls[0] == f"with_timeout:{vault.ingest_request_timeout}"


def test_ingest_segment_failure_leaves_wiki_untouched(vault):
    # A multi-segment ingest is atomic: if a later segment's model pass fails, the
    # concept pages an earlier segment produced must NOT be on disk, and there must
    # be no source page, ledger record, or log entry — nothing half-written.
    vault.ingest_segment_max_tokens = 50  # force a 2-segment split (~200 chars each)
    page1 = "<!-- page 1 -->\n" + "Active recall is described here. " * 12
    page2 = "<!-- page 2 -->\n" + "Spaced repetition is described here. " * 12
    src = vault.root / "book.md"
    src.write_text(page1 + "\n\n" + page2, "utf-8")

    class _FailSecondSegment(_ScriptedProvider):
        def parse(self, system, user, schema, *, model=None, max_tokens=16000):
            # Sequence is a1, g1, a2 — blow up on the 2nd segment's analysis, after
            # segment 1 has fully compiled (its pages are only in memory, unwritten).
            if schema is SourceAnalysis and self.calls.count("parse:SourceAnalysis") == 1:
                raise ProviderError("simulated mid-ingest failure")
            return super().parse(system, user, schema, model=model, max_tokens=max_tokens)

    provider = _FailSecondSegment(
        analyses=[
            SourceAnalysis(source_title="Guide", source_summary="Part 1.", concept_titles=["Active Recall"]),
            SourceAnalysis(source_title="Guide", source_summary="Part 2.", concept_titles=["Spaced Repetition"]),
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Active Recall", body="Active recall body.")],
                source_page=SourcePageDraft(summary="Covers active recall.", grounds=["Active Recall"]),
            ),
        ],
    )

    log_before = vault.log_file.read_text("utf-8") if vault.log_file.exists() else ""

    with pytest.raises(ProviderError):
        ingest(vault, provider, str(src), section="academic/learning")

    # Segment 1's concept was compiled but never written — the wiki is untouched.
    assert read_page(concept_path(vault, "academic/learning", "Active Recall")) is None
    assert read_page(source_path(vault, "academic/learning", "book")) is None
    # No ledger commit at all: the state file is never written when ingest aborts.
    sources = (
        json.loads(vault.state_file.read_text("utf-8")).get("sources", {})
        if vault.state_file.exists()
        else {}
    )
    assert "raw/sources/book.md" not in sources
    log_after = vault.log_file.read_text("utf-8") if vault.log_file.exists() else ""
    assert log_after == log_before


def test_segment_markdown_splits_on_page_markers():
    page1 = "<!-- page 1 -->\n" + "a" * 300
    page2 = "<!-- page 2 -->\n" + "b" * 300
    segs = segment_markdown(f"{page1}\n\n{page2}", max_chars=400)
    assert len(segs) == 2
    assert segs[0].startswith("<!-- page 1 -->")
    assert segs[1].startswith("<!-- page 2 -->")
    assert all(len(s) <= 400 for s in segs)


def test_segment_markdown_keeps_small_source_whole():
    assert segment_markdown("# Tiny\n\nbody", max_chars=10_000) == ["# Tiny\n\nbody"]


def test_segment_markdown_packs_pages_to_budget():
    # Several small pages pack into fewer segments rather than one-per-page.
    pages = "\n\n".join(f"<!-- page {i} -->\nshort text" for i in range(1, 9))
    segs = segment_markdown(pages, max_chars=120)
    assert 1 < len(segs) < 8  # packed, not split per page nor left whole


def test_segment_markdown_does_not_break_display_math():
    block = "<!-- page 1 -->\n$$\n" + "x+1=2 \\\\\n" * 40 + "$$"
    segs = segment_markdown(block + "\n\n<!-- page 2 -->\ntail", max_chars=100)
    # Every segment keeps $$ fences balanced (math never split mid-block).
    assert all(s.count("$$") % 2 == 0 for s in segs)
