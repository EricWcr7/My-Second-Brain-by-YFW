"""Ingest pipeline: normalize a source, compile it into concept/source pages.

Two LLM passes (per the schema): an analysis pass that decides which concepts the
source teaches, then a generation pass that writes/merges the pages. File writes
and index/log updates are deterministic.
"""

from __future__ import annotations

import datetime as _dt
import os
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path

from pydantic import BaseModel, Field

from . import overrides
from .chunking import segment_markdown
from .config import Config
from .embeddings import make_embedder
from .indexing import index_pages
from .loaders import LoadResult, is_url, load_source
from .loaders.registry import IMAGE_EXTS
from .overview import refresh_overview
from .providers.base import LLMProvider
from .store import (
    ensure_dir,
    get_source_record,
    load_state,
    read_page,
    save_state,
    set_source_record,
    sha256_bytes,
    sha256_file,
    write_page,
)
from .wiki import (
    append_log,
    concept_path,
    iter_pages,
    normalize_section,
    rebuild_index,
    section_ancestry,
    slugify,
    source_path,
    today,
)

LARGE_TOKEN_WARN = 200_000
# Rough bytes-per-token used to turn the token budget into a character budget for
# the deterministic source split (avoids a provider token-count per segment).
_CHARS_PER_TOKEN = 4


# --- structured outputs ------------------------------------------------------


class SourceAnalysis(BaseModel):
    source_title: str
    source_summary: str
    concept_titles: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class ConceptDraft(BaseModel):
    title: str
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    related_source_slugs: list[str] = Field(default_factory=list)
    body: str


class SourcePageDraft(BaseModel):
    summary: str
    grounds: list[str] = Field(default_factory=list)


class GenerationResult(BaseModel):
    concept_pages: list[ConceptDraft] = Field(default_factory=list)
    source_page: SourcePageDraft
    log_entry: str = ""


@dataclass
class IngestResult:
    status: str  # "ingested" | "skipped"
    source_key: str
    source_slug: str | None = None
    title: str = ""
    concept_slugs: list[str] = field(default_factory=list)
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


# --- helpers -----------------------------------------------------------------


def _system(instruction_file: str, config: Config, section: str) -> str:
    # ``instruction_file`` is "<component>.md"; resolve the operation prompt plus
    # purpose/schema against this section's overrides (falling back to general).
    component = Path(instruction_file).stem
    parts = [
        overrides.effective(config, section, component),
        overrides.effective(config, section, "purpose"),
        overrides.effective(config, section, "schema"),
    ]
    return "\n\n".join(p for p in parts if p.strip()).strip()


def _clean_slug(value: str) -> str:
    return value.strip().strip("[]").split("|", 1)[0].split("#", 1)[0].strip()


def _resolve_raw(config: Config, spec: str) -> tuple[Path | None, str, str]:
    """Return (raw_path, ledger_key, raw_ref). Copies external files into raw/.

    Image files land under ``raw/assets/`` so they can be embedded and viewed
    directly; every other source type lands under ``raw/sources/``.
    """
    if is_url(spec):
        return None, spec, spec
    src = Path(spec).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"No such file: {src}")
    src = src.resolve()
    raw_dir = config.raw_dir.resolve()
    if raw_dir in src.parents:
        path = src
    else:
        dest_dir = config.assets_dir if src.suffix.lower() in IMAGE_EXTS else config.sources_dir
        ensure_dir(dest_dir)
        dest = dest_dir / src.name
        if dest.exists() and sha256_file(dest) != sha256_file(src):
            dest = dest_dir / f"{src.stem}-{sha256_file(src)[:8]}{src.suffix}"
        if not dest.exists():
            shutil.copy2(src, dest)
        path = dest.resolve()
    rel = path.relative_to(config.root.resolve()).as_posix()
    return path, rel, rel


def _instruction_block(user_prompt: str | None) -> str:
    # Optional free-text guidance from the user, placed at the top of the user
    # message so the model reads it before the source. Empty when absent, so an
    # un-guided ingest produces a byte-for-byte unchanged prompt.
    if not user_prompt:
        return ""
    return (
        "User instruction (honor it where it doesn't conflict with grounding):\n"
        f"{user_prompt}\n\n"
    )


def _analysis_user(
    section: str,
    loaded: LoadResult,
    existing_titles: list[str],
    user_prompt: str | None = None,
) -> str:
    existing = "\n".join(f"- {t}" for t in existing_titles) or "(none yet)"
    return (
        _instruction_block(user_prompt)
        + f"Section: {section or 'General'}\n"
        f"Source title: {loaded.title}\n"
        f"Source kind: {loaded.kind}\n\n"
        f"Existing concept titles in this section:\n{existing}\n\n"
        f"--- SOURCE START ---\n{loaded.markdown}\n--- SOURCE END ---\n"
    )


def _generation_user(
    section: str,
    source_slug: str,
    loaded: LoadResult,
    analysis: SourceAnalysis,
    existing_pages: list[tuple[str, str, str]],
    index_titles: list[str],
    user_prompt: str | None = None,
) -> str:
    idx = "\n".join(f"- {t}" for t in index_titles) or "(none yet)"
    existing_blocks = [
        f"### Existing page: {title} (slug: {slug})\n{body}"
        for slug, title, body in existing_pages
    ]
    existing_text = "\n\n".join(existing_blocks) or "(no existing pages to merge)"
    concept_list = "\n".join(f"- {t}" for t in analysis.concept_titles) or "(decide from source)"
    return (
        _instruction_block(user_prompt)
        + f"Section: {section or 'General'}\n"
        f"This source's provenance slug: {source_slug}\n"
        f"Source title: {loaded.title} (kind: {loaded.kind})\n\n"
        f"Analysis summary: {analysis.source_summary}\n"
        f"Concepts to write/update:\n{concept_list}\n\n"
        f"Existing concept index (slug :: title) for linking:\n{idx}\n\n"
        f"Existing page bodies to merge:\n{existing_text}\n\n"
        f"--- SOURCE START ---\n{loaded.markdown}\n--- SOURCE END ---\n"
    )


def _write_source_page(
    config: Config,
    section: str,
    source_slug: str,
    loaded: LoadResult,
    raw_ref: str,
    draft: SourcePageDraft,
) -> None:
    body = draft.summary.strip()
    grounds = [f"- [[{slugify(t)}|{t}]]" for t in draft.grounds]
    if grounds:
        body += "\n\n## Concepts\n\n" + "\n".join(grounds)
    metadata = {
        "title": loaded.title,
        "type": "source",
        "section": section,
        "kind": loaded.kind,
        "path": raw_ref,
        "ingested": today(),
    }
    page_path = source_path(config, section, source_slug)
    if loaded.kind == "image":
        # Embed the captured asset so it is viewable in the wiki, and record it
        # in frontmatter for provenance. The path is relative to the source page.
        asset_abs = (config.root / raw_ref).resolve()
        rel = os.path.relpath(asset_abs, page_path.parent)
        body = f"![{loaded.title}]({rel})\n\n{body}"
        metadata["assets"] = [raw_ref]
    write_page(page_path, metadata, body + "\n")


def _write_concept_page(
    config: Config, section: str, source_slug: str, draft: ConceptDraft
) -> str:
    path = concept_path(config, section, draft.title)
    existing = read_page(path)
    sources: set[str] = set()
    if existing:
        prev = existing.metadata.get("sources") or []
        if isinstance(prev, list):
            sources.update(_clean_slug(str(s)) for s in prev)
    sources.add(source_slug)
    sources.update(_clean_slug(s) for s in draft.related_source_slugs if s.strip())
    sources.discard("")
    metadata = {
        "title": draft.title,
        "type": "concept",
        "section": section,
        "tags": list(draft.tags),
        "aliases": list(draft.aliases),
        "sources": sorted(sources),
        "updated": today(),
    }
    write_page(path, metadata, draft.body.strip() + "\n")
    return slugify(draft.title)


def _merge_source_drafts(drafts: list[SourcePageDraft]) -> SourcePageDraft:
    """Fold per-segment source-page drafts into one page for the whole source.

    A segmented ingest produces one draft per segment; the source has a single
    provenance page, so concatenate the part summaries and union the grounded
    concepts (deduped by slug, order preserved).
    """
    if len(drafts) == 1:
        return drafts[0]
    summaries = [d.summary.strip() for d in drafts if d.summary.strip()]
    if len(summaries) > 1:
        summary = (
            f"This source was large and compiled in {len(drafts)} parts.\n\n"
            + "\n\n".join(f"**Part {i}.** {s}" for i, s in enumerate(summaries, 1))
        )
    else:
        summary = summaries[0] if summaries else ""
    seen: set[str] = set()
    grounds: list[str] = []
    for draft in drafts:
        for title in draft.grounds:
            slug = slugify(title)
            if slug and slug not in seen:
                seen.add(slug)
                grounds.append(title)
    return SourcePageDraft(summary=summary, grounds=grounds)


# --- entry point -------------------------------------------------------------


def ingest(
    config: Config,
    provider: LLMProvider,
    spec: str,
    *,
    section: str | None = None,
    force_vision: bool = False,
    force: bool = False,
    user_prompt: str | None = None,
) -> IngestResult:
    # Canonicalize once so placement, frontmatter, and section comparisons all
    # agree — iter_pages returns normalized sections, so a raw caller string
    # (e.g. "academic//calc notes/") would otherwise miss existing concepts.
    section = normalize_section(section if section is not None else config.default_section)
    warnings: list[str] = []

    # Ingest runs many slow model passes (multi-segment compilation, per-page
    # vision transcription), so scope a longer per-request timeout to this call —
    # the interactive query/lint paths keep the shorter ``request_timeout``.
    provider = provider.with_timeout(config.ingest_request_timeout)

    raw_path, key, raw_ref = _resolve_raw(config, spec)
    load_spec = spec if is_url(spec) else str(raw_path)
    loaded = load_source(
        load_spec, config=config, provider=provider, force_vision=force_vision
    )

    if is_url(spec):
        checksum = sha256_bytes(loaded.markdown.encode("utf-8"))
        source_slug = slugify(loaded.title)
    else:
        checksum = sha256_file(raw_path)  # type: ignore[arg-type]
        source_slug = slugify(raw_path.stem)  # type: ignore[union-attr]

    state = load_state(config)
    rec = get_source_record(state, key)
    if rec and rec.get("checksum") == checksum and not force:
        return IngestResult(
            status="skipped",
            source_key=key,
            source_slug=rec.get("source_slug"),
            title=loaded.title,
            reason="unchanged",
        )

    ensure_dir(config.normalized_dir)
    (config.normalized_dir / f"{checksum}.md").write_text(loaded.markdown, "utf-8")

    try:
        n_tokens = provider.count_tokens("", loaded.markdown)
        if n_tokens > LARGE_TOKEN_WARN:
            warnings.append(
                f"Source is large (~{n_tokens} tokens); ingest may be slow and costly."
            )
    except Exception:  # count_tokens is best-effort
        pass

    segments = segment_markdown(
        loaded.markdown, max_chars=config.ingest_segment_max_tokens * _CHARS_PER_TOKEN
    )
    if len(segments) > 1:
        warnings.append(
            f"Large source compiled in {len(segments)} segments to stay within the "
            "model's context window."
        )

    # Compile each segment with the same two passes. To keep a multi-segment
    # ingest atomic, NOTHING is written during the loop: results accumulate in
    # memory and every file write happens afterward, once all model passes have
    # succeeded — so a mid-loop failure leaves the wiki untouched. Earlier
    # segments' concepts are folded into later ones through the prompt context,
    # fed from the accumulator below instead of from disk, so the source still
    # collapses to one provenance record with concepts merged together.
    pre_refs = [r for r in iter_pages(config, "concept") if r.section == section]
    accumulated: dict[str, ConceptDraft] = {}
    source_drafts: list[SourcePageDraft] = []
    log_entry = ""

    def _visible_concepts() -> tuple[list[str], list[str]]:
        # Section concepts the next segment can link/merge: those on disk when the
        # ingest started, plus the ones earlier segments produced (still in
        # memory). The accumulator overrides disk for a shared slug — its draft is
        # the newer version. Returns (titles, "slug :: title" index lines).
        by_slug: dict[str, str] = {r.slug: r.title for r in pre_refs}
        for d in accumulated.values():
            by_slug[slugify(d.title)] = d.title
        return list(by_slug.values()), [f"{s} :: {t}" for s, t in by_slug.items()]

    for segment in segments:
        seg_loaded = replace(loaded, markdown=segment)
        existing_titles, index_titles = _visible_concepts()
        analysis = provider.parse(
            _system("ingest_analysis.md", config, section),
            _analysis_user(section, seg_loaded, existing_titles, user_prompt),
            SourceAnalysis,
        )
        existing_pages: list[tuple[str, str, str]] = []
        for title in analysis.concept_titles:
            slug = slugify(title)
            if slug in accumulated:
                draft = accumulated[slug]
                existing_pages.append((slug, draft.title, draft.body))
            else:
                page = read_page(concept_path(config, section, title))
                if page:
                    existing_pages.append((slug, title, page.content))
        gen = provider.parse(
            _system("ingest_generation.md", config, section),
            _generation_user(
                section,
                source_slug,
                seg_loaded,
                analysis,
                existing_pages,
                index_titles,
                user_prompt,
            ),
            GenerationResult,
        )
        for draft in gen.concept_pages:
            slug = slugify(draft.title)
            prev = accumulated.get(slug)
            if prev is not None:
                # Last segment wins on body/tags/aliases (matching the on-disk
                # last-write), but keep every source this concept was grounded in.
                related = list(
                    dict.fromkeys([*prev.related_source_slugs, *draft.related_source_slugs])
                )
                accumulated[slug] = draft.model_copy(update={"related_source_slugs": related})
            else:
                accumulated[slug] = draft
        source_drafts.append(gen.source_page)
        if gen.log_entry.strip():
            log_entry = gen.log_entry.strip()

    # Every segment compiled cleanly — now the deterministic writes (the wiki's
    # commit point for this source).
    touched = [
        _write_concept_page(config, section, source_slug, draft)
        for draft in accumulated.values()
    ]
    _write_source_page(
        config, section, source_slug, loaded, raw_ref, _merge_source_drafts(source_drafts)
    )

    detail = log_entry or (
        f"concepts: {', '.join(touched) or 'none'} (section: {section or 'General'})"
    )
    if len(segments) > 1:
        detail += f" [{len(segments)} segments]"
    if user_prompt:
        # Record the guidance that shaped these pages (collapsed to one line so the
        # log.md bullet stays single-line).
        detail += f" | guidance: {' '.join(user_prompt.split())}"
    append_log(config, "ingest", loaded.title, detail=detail)
    rebuild_index(config)

    # Vector indexing is a best-effort post-step: embed the touched concept pages
    # so semantic search sees them. It never blocks ingest — a missing search
    # extra or embeddings key just leaves the wiki keyword-searchable.
    embedder = make_embedder(config)
    if embedder is not None and touched:
        try:
            refs = [
                r
                for r in iter_pages(config, "concept")
                if r.slug in set(touched) and r.section == section
            ]
            index_pages(config, embedder, refs)
        except Exception as e:  # pragma: no cover - resilience path
            warnings.append(f"vector indexing skipped: {e}")

    # Section overviews are LLM-maintained: refresh the ingested section and every
    # ancestor up to General (each summarizes everything beneath it). Best-effort,
    # like vector indexing above — a failure here must never undo a committed
    # ingest, so it degrades to a warning.
    for sec in section_ancestry(section):
        try:
            refresh_overview(config, provider, sec)
        except Exception as e:  # pragma: no cover - resilience path
            warnings.append(f"overview refresh skipped for {sec or 'General'}: {e}")

    set_source_record(
        state,
        key,
        {
            "checksum": checksum,
            "kind": loaded.kind,
            "title": loaded.title,
            "section": section,
            "raw_ref": raw_ref,
            "source_slug": source_slug,
            "concept_slugs": touched,
            "ingested_at": _dt.datetime.now().isoformat(timespec="seconds"),
        },
    )
    save_state(config, state)

    return IngestResult(
        status="ingested",
        source_key=key,
        source_slug=source_slug,
        title=loaded.title,
        concept_slugs=touched,
        warnings=warnings,
    )
