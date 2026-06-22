"""LLM reranking: reorder hybrid-search candidates by relevance to the question.

A cheap first-stage retrieval (BM25 ⊕ vector, fused with RRF) is good at *recall*
but blunt at ordering — it can't tell that page A actually answers the question
better than page B. This optional second stage reads the question and each
candidate's title + snippet and returns the candidates ranked by relevance, so the
most useful pages win the answer's limited context budget.

It is **opt-in** (``config.rerank``) and provider-abstracted — it reuses the chat
provider rather than adding an external reranker, so it works on every backend and
is faked in tests/evals. It only **reorders** the candidates: every slug returned
is validated against the candidate set, and any the model omits are appended in
their original order, so reranking can never invent, drop, or duplicate a page. Any
failure degrades to the original retrieval order — reranking never breaks Ask.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from .config import Config
from .providers.base import LLMProvider
from .search import SearchHit
from .store import read_page

logger = logging.getLogger("llmwiki.rerank")

# How much of each candidate page the model sees — enough to judge relevance
# without spending the whole context budget on the rerank call itself.
_SNIPPET_CHARS = 600

_RERANK_SYSTEM = (
    "You are reranking candidate wiki pages for relevance to a question. You are "
    "given the question and a numbered list of candidate pages, each with a "
    "[[slug]], title, and snippet. Return the candidate slugs ordered from most to "
    "least relevant for answering the question. Use ONLY the slugs provided — never "
    "invent, rename, or drop a slug. Output just the ordered list of slugs."
)


class RerankResult(BaseModel):
    """The candidate slugs, ordered most-relevant-first."""

    slugs: list[str] = Field(default_factory=list)


def _clean_slug(value: str) -> str:
    # Tolerate the model echoing a full wikilink: ``[[slug|Alias]]`` / ``slug#anchor``.
    return value.strip().strip("[]").split("|", 1)[0].split("#", 1)[0].strip()


def _candidate_block(hits: list[SearchHit]) -> str:
    lines: list[str] = []
    for i, hit in enumerate(hits, 1):
        page = read_page(hit.ref.path)
        snippet = (page.content[:_SNIPPET_CHARS].strip() + " …") if page else "(no body)"
        lines.append(f"{i}. [[{hit.ref.slug}]] — {hit.ref.title}\n{snippet}")
    return "\n\n".join(lines)


def rerank_hits(
    config: Config,
    provider: LLMProvider,
    question: str,
    hits: list[SearchHit],
) -> list[SearchHit]:
    """Return ``hits`` reordered by LLM-judged relevance to ``question``.

    Pure reordering: the result is a permutation of the input. On any error the
    input order is returned unchanged.
    """
    if len(hits) < 2:
        return hits
    try:
        user = (
            f"Question: {question}\n\n"
            f"Candidate pages:\n\n{_candidate_block(hits)}"
        )
        result = provider.parse(_RERANK_SYSTEM, user, RerankResult)
    except Exception:  # best-effort: a rerank failure must never break Ask
        logger.debug("rerank unavailable; keeping retrieval order", exc_info=True)
        return hits

    by_slug = {hit.ref.slug: hit for hit in hits}
    ordered: list[SearchHit] = []
    seen: set[str] = set()
    for raw in result.slugs:
        slug = _clean_slug(raw)
        hit = by_slug.get(slug)
        if hit is not None and slug not in seen:
            seen.add(slug)
            ordered.append(hit)
    # Append any candidates the model left out, preserving their retrieval order, so
    # reranking never silently drops a page.
    for hit in hits:
        if hit.ref.slug not in seen:
            ordered.append(hit)
            seen.add(hit.ref.slug)
    return ordered
