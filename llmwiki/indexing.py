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
from .embeddings import Embedder
from .store import read_page
from .vectorindex import VectorIndex, open_index
from .wiki import PageRef, iter_pages


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


def reindex_page(
    index: VectorIndex,
    embedder: Embedder,
    config: Config,
    ref: PageRef,
    *,
    existing: dict[str, str] | None = None,
    force: bool = False,
) -> int:
    """(Re)embed one page's chunks into its section's model table.

    Returns the number of chunks embedded (0 = skipped because nothing changed, or
    the page is empty/gone).
    """
    model = config.embed_model
    page = read_page(ref.path)
    if page is None:
        index.upsert_page(model, ref.slug, [])
        return 0

    chunks = chunk_page(ref, page.content, max_chars=config.chunk_max_chars)
    if existing is None:
        existing = index.existing_hashes(model)
    want = {c.id: c.content_hash for c in chunks}
    have = {cid: h for cid, h in existing.items() if cid.startswith(ref.slug + "#")}
    if not force and want == have and chunks:
        return 0

    vectors = embedder.embed([c.embed_text() for c in chunks], model=model)
    index.upsert_page(model, ref.slug, _rows_for(chunks, vectors))
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
    index = open_index(config)
    existing = index.existing_hashes(config.embed_model)
    result = ReindexResult()
    for ref in refs:
        n = reindex_page(index, embedder, config, ref, existing=existing, force=force)
        result.pages += 1
        result.chunks += n
        if n == 0:
            result.skipped += 1
    return result


def reindex_all(
    config: Config, embedder: Embedder, *, force: bool = False
) -> ReindexResult:
    """Rebuild the index from all concept pages, dropping chunks for deleted pages."""
    refs = iter_pages(config, "concept")
    result = index_pages(config, embedder, refs, force=force)

    # Drop any chunks whose page no longer exists on disk (deletion sweep).
    index = open_index(config)
    current = {ref.slug for ref in refs}
    stored = {cid.split("#", 1)[0] for cid in index.existing_hashes(config.embed_model)}
    index.delete_page_slugs(stored - current)
    return result
