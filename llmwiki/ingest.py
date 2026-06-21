"""Ingest pipeline: normalize a source, compile it into concept/source pages.

Two LLM passes (per the schema): an analysis pass that decides which concepts the
source teaches, then a generation pass that writes/merges the pages. File writes
and index/log updates are deterministic.
"""

from __future__ import annotations

import datetime as _dt
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from . import overrides
from .config import Config
from .embeddings import make_embedder
from .indexing import index_pages
from .loaders import LoadResult, is_url, load_source
from .loaders.registry import IMAGE_EXTS
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
    slugify,
    source_path,
    today,
)

LARGE_TOKEN_WARN = 200_000


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
    overview: str | None = None
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


def _analysis_user(section: str, loaded: LoadResult, existing_titles: list[str]) -> str:
    existing = "\n".join(f"- {t}" for t in existing_titles) or "(none yet)"
    return (
        f"Section: {section or 'General'}\n"
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
) -> str:
    idx = "\n".join(f"- {t}" for t in index_titles) or "(none yet)"
    existing_blocks = [
        f"### Existing page: {title} (slug: {slug})\n{body}"
        for slug, title, body in existing_pages
    ]
    existing_text = "\n\n".join(existing_blocks) or "(no existing pages to merge)"
    concept_list = "\n".join(f"- {t}" for t in analysis.concept_titles) or "(decide from source)"
    return (
        f"Section: {section or 'General'}\n"
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


# --- entry point -------------------------------------------------------------


def ingest(
    config: Config,
    provider: LLMProvider,
    spec: str,
    *,
    section: str | None = None,
    force_vision: bool = False,
    force: bool = False,
) -> IngestResult:
    section = section if section is not None else config.default_section
    warnings: list[str] = []

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

    existing_titles = [r.title for r in iter_pages(config, "concept") if r.section == section]

    analysis = provider.parse(
        _system("ingest_analysis.md", config, section),
        _analysis_user(section, loaded, existing_titles),
        SourceAnalysis,
    )

    existing_pages: list[tuple[str, str, str]] = []
    for title in analysis.concept_titles:
        page = read_page(concept_path(config, section, title))
        if page:
            existing_pages.append((slugify(title), title, page.content))

    index_titles = [
        f"{r.slug} :: {r.title}" for r in iter_pages(config, "concept") if r.section == section
    ]

    gen = provider.parse(
        _system("ingest_generation.md", config, section),
        _generation_user(
            section, source_slug, loaded, analysis, existing_pages, index_titles
        ),
        GenerationResult,
    )

    _write_source_page(config, section, source_slug, loaded, raw_ref, gen.source_page)

    touched: list[str] = []
    for draft in gen.concept_pages:
        touched.append(_write_concept_page(config, section, source_slug, draft))

    if gen.overview and gen.overview.strip():
        config.overview_file.write_text(gen.overview.strip() + "\n", "utf-8")

    detail = gen.log_entry.strip() or (
        f"concepts: {', '.join(touched) or 'none'} (section: {section or 'General'})"
    )
    append_log(config, "ingest", loaded.title, detail=detail)
    rebuild_index(config)

    # Vector indexing is a best-effort post-step: embed the touched concept pages
    # so semantic search sees them. It never blocks ingest — a missing search
    # extra or embeddings key just leaves the wiki keyword-searchable.
    embedder = make_embedder(config)
    if embedder is not None and touched:
        norm = normalize_section(section)
        try:
            refs = [
                r
                for r in iter_pages(config, "concept")
                if r.slug in set(touched) and r.section == norm
            ]
            index_pages(config, embedder, refs)
        except Exception as e:  # pragma: no cover - resilience path
            warnings.append(f"vector indexing skipped: {e}")

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
