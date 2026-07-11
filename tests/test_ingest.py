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
    result = ingest(vault, provider, str(src), section="academic/calc")

    assert result.status == "ingested"
    assert result.source_slug == "note"
    assert result.concept_slugs == ["chain-rule"]

    concept = read_page(concept_path(vault, "academic/calc", "Chain Rule"))
    assert concept is not None
    assert concept.metadata["type"] == "concept"
    assert concept.metadata["section"] == "academic/calc"
    assert "note" in concept.metadata["sources"]  # provenance back to the source

    source = read_page(source_path(vault, "academic/calc", "note"))
    assert source is not None
    assert source.metadata["type"] == "source"
    assert source.metadata["path"] == "raw/sources/note.md"

    assert "chain-rule" in vault.index_file.read_text("utf-8")

    # The operation is journaled as a greppable log entry.
    log_text = vault.log_file.read_text("utf-8")
    assert any(line.startswith("## [") and "ingest |" in line for line in log_text.splitlines())
    assert "Ingested chain rule notes." in log_text  # gen.log_entry becomes the detail line


def test_ingest_normalizes_the_section_argument(vault):
    # The web UI sends canonical sections, but the CLI can pass raw text. ingest()
    # canonicalizes once up front, so placement and frontmatter use the normalized
    # form (iter_pages normalizes on read — a raw string would diverge from disk).
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nbody", "utf-8")

    result = ingest(vault, _provider(), str(src), section="academic//calc notes/")
    assert result.status == "ingested"

    concept = read_page(concept_path(vault, "academic/calc-notes", "Chain Rule"))
    assert concept is not None
    assert concept.metadata["section"] == "academic/calc-notes"

    source = read_page(source_path(vault, "academic/calc-notes", "note"))
    assert source is not None
    assert source.metadata["section"] == "academic/calc-notes"


def test_ingest_skips_unchanged_source(vault):
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nUnchanged content.", "utf-8")

    first = ingest(vault, _provider(), str(src), section="academic/calc")
    assert first.status == "ingested"

    second = ingest(vault, _provider(), str(src), section="academic/calc")
    assert second.status == "skipped"
    assert second.reason == "unchanged"


def test_ingest_copies_external_file_into_raw(vault, tmp_path):
    external = tmp_path.parent / "external_note.md"
    external.write_text("# Topic\n\nbody", "utf-8")

    ingest(vault, _provider(), str(external), section="academic/calc")
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

    ingest(vault, provider, str(img), section="academic/calc")

    # Images are stored under raw/assets/, not raw/sources/.
    assert (vault.assets_dir / "diagram.png").exists()
    assert not (vault.sources_dir / "diagram.png").exists()

    source = read_page(source_path(vault, "academic/calc", "diagram"))
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
    page1 = "<!-- page 1 -->\n" + "Open sets are defined here. " * 12
    page2 = "<!-- page 2 -->\n" + "Compact sets are defined here. " * 12
    src = vault.root / "book.md"
    src.write_text(page1 + "\n\n" + page2, "utf-8")

    provider = _ScriptedProvider(
        analyses=[
            SourceAnalysis(source_title="Book", source_summary="Part 1.", concept_titles=["Open Sets"]),
            SourceAnalysis(source_title="Book", source_summary="Part 2.", concept_titles=["Compact Sets"]),
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Open Sets", body="Open sets body.")],
                source_page=SourcePageDraft(summary="Covers open sets.", grounds=["Open Sets"]),
            ),
            GenerationResult(
                concept_pages=[ConceptDraft(title="Compact Sets", body="Compact sets body.")],
                source_page=SourcePageDraft(summary="Covers compact sets.", grounds=["Compact Sets"]),
            ),
        ],
    )
    result = ingest(vault, provider, str(src), section="academic/calc")

    # Two segments => two analysis + two generation passes.
    assert provider.calls.count("parse:SourceAnalysis") == 2
    assert provider.calls.count("parse:GenerationResult") == 2

    # Both concepts written, under one source slug.
    assert set(result.concept_slugs) == {"open-sets", "compact-sets"}
    assert read_page(concept_path(vault, "academic/calc", "Open Sets")) is not None
    assert read_page(concept_path(vault, "academic/calc", "Compact Sets")) is not None

    # ONE provenance record for the whole source.
    sources = json.loads(vault.state_file.read_text("utf-8"))["sources"]
    assert list(sources) == ["raw/sources/book.md"]
    assert set(sources["raw/sources/book.md"]["concept_slugs"]) == {"open-sets", "compact-sets"}

    # ONE source page, summarizing both parts and linking both concepts.
    source = read_page(source_path(vault, "academic/calc", "book"))
    assert source is not None
    assert "Covers open sets." in source.content and "Covers compact sets." in source.content
    assert "[[open-sets" in source.content and "[[compact-sets" in source.content

    # Accumulation wiring: the 2nd segment's analysis was told "Open Sets" already
    # exists (it was written by segment 1). Call order: a1, g1, a2, g2.
    assert "Open Sets" in provider.user_prompts[2]


def _single_segment_provider() -> "_ScriptedProvider":
    return _ScriptedProvider(
        analyses=[
            SourceAnalysis(
                source_title="Chain Rule Notes",
                source_summary="Notes on the chain rule.",
                concept_titles=["Chain Rule"],
            )
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Chain Rule", body="Chain rule body.")],
                source_page=SourcePageDraft(summary="Covers the chain rule.", grounds=["Chain Rule"]),
                log_entry="Ingested chain rule notes.",
            )
        ],
    )


def test_ingest_threads_user_prompt_into_both_passes(vault):
    # An optional user instruction rides into BOTH compile passes (analysis at
    # index 0, generation at index 1) and is journaled for provenance.
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nThe chain rule differentiates compositions.", "utf-8")

    provider = _single_segment_provider()
    ingest(vault, provider, str(src), section="academic/calc", user_prompt="focus on the proofs")

    assert "User instruction" in provider.user_prompts[0]
    assert "focus on the proofs" in provider.user_prompts[0]
    assert "focus on the proofs" in provider.user_prompts[1]

    assert "guidance: focus on the proofs" in vault.log_file.read_text("utf-8")


def test_ingest_without_user_prompt_leaves_prompts_and_log_unchanged(vault):
    # The default (no guidance) path must be byte-for-byte unchanged: no
    # instruction block in the prompts and no guidance line in the log.
    src = vault.root / "note.md"
    src.write_text("# Chain Rule\n\nThe chain rule differentiates compositions.", "utf-8")

    provider = _single_segment_provider()
    ingest(vault, provider, str(src), section="academic/calc")

    assert "User instruction" not in provider.user_prompts[0]
    assert "User instruction" not in provider.user_prompts[1]
    assert "guidance:" not in vault.log_file.read_text("utf-8")


def test_ingest_sees_existing_concepts_despite_raw_section_spelling(vault):
    # The existing-concepts context fed to the analysis pass filters pages by
    # section. iter_pages returns normalized sections, so a raw caller spelling
    # ("academic//calc") must still match concepts filed under "academic/calc".
    seed = vault.root / "note.md"
    seed.write_text("# Chain Rule\n\nThe chain rule.", "utf-8")
    ingest(vault, _provider(), str(seed), section="academic/calc")

    other = vault.root / "integrals.md"
    other.write_text("# Integrals\n\nIntegration by parts.", "utf-8")
    provider = _ScriptedProvider(
        analyses=[
            SourceAnalysis(source_title="Integrals", source_summary="s", concept_titles=["Integrals"])
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Integrals", body="body")],
                source_page=SourcePageDraft(summary="s", grounds=["Integrals"]),
            )
        ],
    )
    ingest(vault, provider, str(other), section="academic//calc")

    # The seeded concept is visible to the analysis pass (the source text itself
    # never mentions it, so this can only come from the existing-concepts block).
    assert "Chain Rule" in provider.user_prompts[0]


def test_ingest_single_segment_unchanged_for_small_source(vault):
    # A source within budget still compiles in exactly one analysis + generation
    # pass (no behavior change for the common case).
    src = vault.root / "small.md"
    src.write_text("# Chain Rule\n\nShort note.", "utf-8")
    provider = _ScriptedProvider(
        analyses=[SourceAnalysis(source_title="N", source_summary="s", concept_titles=["Chain Rule"])],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Chain Rule", body="body")],
                source_page=SourcePageDraft(summary="one part", grounds=["Chain Rule"]),
            )
        ],
    )
    ingest(vault, provider, str(src), section="academic/calc")
    # One analysis + one generation pass for the single segment...
    assert provider.calls[:3] == [
        f"with_timeout:{vault.ingest_request_timeout}",
        "parse:SourceAnalysis",
        "parse:GenerationResult",
    ]
    # ...then a best-effort overview refresh for the section and its two ancestors
    # (General + academic), each a `complete` call.
    assert provider.calls.count("complete") == 3
    source = read_page(source_path(vault, "academic/calc", "small"))
    assert source is not None and "one part" in source.content
    assert "compiled in" not in source.content  # no multi-part preamble


def test_ingest_scopes_the_ingest_request_timeout(vault):
    # Ingest rescopes its provider to the longer ingest timeout before any model
    # call (so multi-segment compilation + vision transcription get the headroom),
    # leaving the interactive request_timeout untouched for query/lint.
    src = vault.root / "n.md"
    src.write_text("# Chain Rule\n\nShort.", "utf-8")
    provider = _provider()
    ingest(vault, provider, str(src), section="academic/calc")
    assert provider.calls[0] == f"with_timeout:{vault.ingest_request_timeout}"


def test_ingest_segment_failure_leaves_wiki_untouched(vault):
    # A multi-segment ingest is atomic: if a later segment's model pass fails, the
    # concept pages an earlier segment produced must NOT be on disk, and there must
    # be no source page, ledger record, or log entry — nothing half-written.
    vault.ingest_segment_max_tokens = 50  # force a 2-segment split (~200 chars each)
    page1 = "<!-- page 1 -->\n" + "Open sets are defined here. " * 12
    page2 = "<!-- page 2 -->\n" + "Compact sets are defined here. " * 12
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
            SourceAnalysis(source_title="Book", source_summary="Part 1.", concept_titles=["Open Sets"]),
            SourceAnalysis(source_title="Book", source_summary="Part 2.", concept_titles=["Compact Sets"]),
        ],
        generations=[
            GenerationResult(
                concept_pages=[ConceptDraft(title="Open Sets", body="Open sets body.")],
                source_page=SourcePageDraft(summary="Covers open sets.", grounds=["Open Sets"]),
            ),
        ],
    )

    log_before = vault.log_file.read_text("utf-8") if vault.log_file.exists() else ""

    with pytest.raises(ProviderError):
        ingest(vault, provider, str(src), section="academic/calc")

    # Segment 1's concept was compiled but never written — the wiki is untouched.
    assert read_page(concept_path(vault, "academic/calc", "Open Sets")) is None
    assert read_page(source_path(vault, "academic/calc", "book")) is None
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
