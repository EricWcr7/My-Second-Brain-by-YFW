"""Index orchestration: chunk pages, embed the chunks, persist to the vector index.

Composes the three single-purpose modules — :mod:`chunking` (pure), :mod:`embeddings`
(the only LLM call), and :mod:`vectorindex` (LanceDB IO) — into the operations the
pipelines need: (re)index a page after ingest and rebuild the whole index. Every
section uses the one global embedding model (``config.embed_model``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .chunking import chunk_page
from .config import Config
from .embeddings import Embedder, validate_embedding_vectors
from .store import read_page
from .vectorindex import VECTOR_INDEX_WRITE_LOCK, ROW_FIELDS, VectorIndex, open_index
from .wiki import PageRef, iter_pages, normalize_section, section_contains


def _rows_for(chunks, vectors) -> list[dict]:
    return [
        {
            "id": c.id,
            "page_slug": c.page_slug,
            "section": c.section,
            "page_title": c.page_title,
            "heading": c.heading,
            "content_hash": c.content_hash,
            "vector": v,
        }
        for c, v in zip(chunks, vectors)
    ]


def _metadata_for(chunks) -> dict[str, dict]:
    return {
        chunk.id: {
            "id": chunk.id,
            "page_slug": chunk.page_slug,
            "section": chunk.section,
            "page_title": chunk.page_title,
            "heading": chunk.heading,
            "content_hash": chunk.content_hash,
        }
        for chunk in chunks
    }


def reindex_page(
    index: VectorIndex,
    embedder: Embedder,
    config: Config,
    ref: PageRef,
    *,
    existing: list[dict] | None = None,
    force: bool = False,
) -> int:
    """(Re)embed one page's chunks into its section's model table.

    Returns the number of chunks embedded (0 = skipped because nothing changed, or
    the page is empty/gone).
    """
    model = config.embed_model
    page = read_page(ref.path)
    if page is None:
        index.upsert_page(model, ref.section, ref.slug, [])
        return 0

    chunks = chunk_page(ref, page.content, max_chars=config.chunk_max_chars)
    if existing is None:
        existing = index.metadata_rows(model)
    want = _metadata_for(chunks)
    page_rows = [
        row
        for row in existing
        if row["section"] == ref.section and row["page_slug"] == ref.slug
    ]
    have = {
        row["id"]: {field: row[field] for field in ROW_FIELDS}
        for row in page_rows
    }
    if not force and len(have) == len(page_rows) and want == have and chunks:
        return 0

    vectors = embedder.embed([c.embed_text() for c in chunks], model=model)
    validate_embedding_vectors(vectors, len(chunks), unit="chunks")
    index.upsert_page(model, ref.section, ref.slug, _rows_for(chunks, vectors))
    return len(chunks)


@dataclass
class ReindexResult:
    pages: int = 0
    chunks: int = 0
    skipped: int = 0


def index_pages(
    config: Config, embedder: Embedder, refs: list[PageRef], *, force: bool = False
) -> ReindexResult:
    """Index a specific set of pages (used by the ingest post-step)."""
    with VECTOR_INDEX_WRITE_LOCK:
        index = open_index(config)
        existing = index.metadata_rows(config.embed_model)
        result = ReindexResult()
        for ref in refs:
            n = reindex_page(index, embedder, config, ref, existing=existing, force=force)
            result.pages += 1
            result.chunks += n
            if n == 0:
                result.skipped += 1
            else:
                existing = index.metadata_rows(config.embed_model)
        return result


def reindex_scope(
    config: Config,
    embedder: Embedder,
    section: str = "",
    *,
    force: bool = False,
) -> ReindexResult:
    """Reconcile concept vectors visible within ``section`` and its descendants."""
    with VECTOR_INDEX_WRITE_LOCK:
        scope = normalize_section(section)
        refs = [
            ref
            for ref in iter_pages(config, "concept")
            if section_contains(scope, ref.section)
        ]
        result = index_pages(config, embedder, refs, force=force)

        # Drop stale pages only inside this scope; unrelated sections are neither
        # read by the embedder nor allowed to disable a scoped semantic query.
        index = open_index(config)
        current = {(ref.section, ref.slug) for ref in refs}
        stored = {
            page
            for page in index.stored_pages(config.embed_model)
            if section_contains(scope, page[0])
        }
        index.delete_pages(stored - current)
        return result


def reindex_all(
    config: Config, embedder: Embedder, *, force: bool = False
) -> ReindexResult:
    """Rebuild the index from all concept pages, dropping chunks for deleted pages."""
    return reindex_scope(config, embedder, force=force)
