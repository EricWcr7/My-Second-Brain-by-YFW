"""Hybrid search over the wiki: BM25 keyword ⊕ vector, fused with RRF.

The keyword index is BM25-lite, built in memory on each call (the corpus is small —
hundreds of pages at most), with titles weighted above body text. When an
:class:`~llmwiki.embeddings.Embedder` is supplied, the derived vector index is
incrementally reconciled with Markdown before its ranking is fused with BM25 via
**Reciprocal Rank Fusion**. Without an embedder — or if reconciliation fails —
search warns once and degrades to pure BM25.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .config import Config
from .indexing import reindex_scope
from .store import read_page
from .wiki import PageRef, iter_pages, page_key, section_contains

if TYPE_CHECKING:
    from .embeddings import Embedder

logger = logging.getLogger("llmwiki.search")
_warning_lock = threading.Lock()
_last_vector_warning: str | None = None

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "for", "on",
    "with", "as", "by", "be", "this", "that", "it", "at", "from", "we", "can",
    "if", "then", "so", "such", "its", "into", "how", "what", "which", "when",
}
_TITLE_WEIGHT = 3
_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in _STOPWORDS]


@dataclass
class SearchHit:
    ref: PageRef
    score: float


def _build_docs(config: Config, page_type: str, section: str | None) -> list[tuple[PageRef, list[str]]]:
    docs: list[tuple[PageRef, list[str]]] = []
    for ref in iter_pages(config, page_type):
        if section and not section_contains(section, ref.section):
            continue
        page = read_page(ref.path)
        if page is None:
            continue
        tokens = tokenize(ref.title) * _TITLE_WEIGHT + tokenize(page.content)
        docs.append((ref, tokens))
    return docs


def _bm25_hits(
    config: Config, query: str, page_type: str, section: str | None
) -> list[SearchHit]:
    """Full BM25 ranking (no top_k) of ``page_type`` pages against ``query``."""
    docs = _build_docs(config, page_type, section)
    if not docs:
        return []

    q_terms = set(tokenize(query))
    if not q_terms:
        return []

    n = len(docs)
    avgdl = sum(len(toks) for _, toks in docs) / n
    df: dict[str, int] = {}
    for _, toks in docs:
        for term in set(toks):
            if term in q_terms:
                df[term] = df.get(term, 0) + 1

    hits: list[SearchHit] = []
    for ref, toks in docs:
        dl = len(toks) or 1
        freqs: dict[str, int] = {}
        for tok in toks:
            if tok in q_terms:
                freqs[tok] = freqs.get(tok, 0) + 1
        score = 0.0
        for term, f in freqs.items():
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (f * (_K1 + 1)) / (f + _K1 * (1 - _B + _B * dl / avgdl))
        if score > 0:
            hits.append(SearchHit(ref=ref, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def _rrf(ranked_slug_lists: list[list[str]], k: int) -> dict[str, float]:
    """Reciprocal Rank Fusion: a slug's score is Σ 1/(k + rank) across lists."""
    scores: dict[str, float] = {}
    for slugs in ranked_slug_lists:
        for rank, slug in enumerate(slugs):
            scores[slug] = scores.get(slug, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _vector_page_list(
    config: Config, query: str, scope: str, embedder: "Embedder"
) -> list[str]:
    """Ranked page slugs from semantic search, scope-filtered and aggregated.

    Chunk hits are filtered with ``section_contains`` and collapsed to pages (a
    page's rank = its best-ranked chunk).
    """
    from .vectorindex import open_index

    # The Markdown wiki is authoritative. Reconcile its derived vector index here
    # so Git/worktree edits self-heal before Search or Ask uses vectors. Hashes make
    # the healthy path local-only: unchanged pages are not re-embedded.
    reindex_scope(config, embedder, scope)
    index = open_index(config)
    qvec = embedder.embed([query], model=config.embed_model)[0]
    order: list[str] = []
    seen: set[str] = set()
    for row in index.search(config.embed_model, qvec, config.vector_top_n):
        if not section_contains(scope, row["section"]):
            continue
        key = page_key(row["section"], row["page_slug"])
        if key not in seen:
            seen.add(key)
            order.append(key)
    return order


def _clear_vector_warning() -> None:
    global _last_vector_warning
    with _warning_lock:
        _last_vector_warning = None


def _warn_vector_fallback(error: Exception) -> None:
    global _last_vector_warning
    message = f"{type(error).__name__}: {error}"
    with _warning_lock:
        if message == _last_vector_warning:
            return
        _last_vector_warning = message
    logger.warning("semantic index unavailable; using BM25 only (%s)", message)


def _hybrid_hits(
    config: Config,
    query: str,
    section: str | None,
    bm25_hits: list[SearchHit],
    embedder: "Embedder",
) -> list[SearchHit]:
    scope = section or ""
    vector_list = _vector_page_list(config, query, scope, embedder)
    _clear_vector_warning()
    if not vector_list:
        return bm25_hits  # nothing indexed yet → keyword only

    scores = _rrf(
        [[page_key(h.ref.section, h.ref.slug) for h in bm25_hits], vector_list],
        config.rrf_k,
    )
    # Resolve fused keys back to concept pages in scope; drop any whose file is
    # gone (self-healing against stale chunks left by a deleted page).
    refs = {
        page_key(r.section, r.slug): r
        for r in iter_pages(config, "concept")
        if section_contains(scope, r.section)
    }
    hits = [SearchHit(ref=refs[s], score=sc) for s, sc in scores.items() if s in refs]
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def search(
    config: Config,
    query: str,
    *,
    page_type: str = "concept",
    top_k: int | None = None,
    section: str | None = None,
    embedder: "Embedder | None" = None,
) -> list[SearchHit]:
    """Rank pages of ``page_type`` against ``query``.

    ``section`` scopes the corpus to that section's subtree (see
    ``wiki.section_contains``); ``None`` searches the whole knowledge base. With an
    ``embedder`` and a populated vector index, BM25 is fused with semantic search
    via RRF (concept pages only); otherwise this is pure BM25.
    """
    bm25_hits = _bm25_hits(config, query, page_type, section)
    hits = bm25_hits
    if embedder is not None and page_type == "concept":
        try:
            hits = _hybrid_hits(config, query, section, bm25_hits, embedder)
        except Exception as error:  # vector path is best-effort; never break search
            _warn_vector_fallback(error)
            logger.debug("vector search failure", exc_info=True)
            hits = bm25_hits
    return hits[:top_k] if top_k is not None else hits
