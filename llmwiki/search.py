"""Keyword search over the wiki (BM25-lite, no embeddings).

The corpus is small (hundreds of pages at most), so the index is built in memory
on each call. Titles are weighted above body text.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .config import Config
from .store import read_page
from .wiki import PageRef, iter_pages

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


def _build_docs(config: Config, page_type: str, course: str | None) -> list[tuple[PageRef, list[str]]]:
    docs: list[tuple[PageRef, list[str]]] = []
    for ref in iter_pages(config, page_type):
        if course and ref.course != course:
            continue
        page = read_page(ref.path)
        if page is None:
            continue
        tokens = tokenize(ref.title) * _TITLE_WEIGHT + tokenize(page.content)
        docs.append((ref, tokens))
    return docs


def search(
    config: Config,
    query: str,
    *,
    page_type: str = "concept",
    top_k: int | None = None,
    course: str | None = None,
) -> list[SearchHit]:
    """Rank pages of ``page_type`` against ``query`` with BM25."""
    docs = _build_docs(config, page_type, course)
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
    if top_k is not None:
        hits = hits[:top_k]
    return hits
