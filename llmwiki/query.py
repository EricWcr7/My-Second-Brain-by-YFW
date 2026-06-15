"""Query pipeline: keyword-retrieve wiki pages, then answer with citations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import prompts
from .config import Config
from .providers.base import LLMProvider
from .search import search
from .store import read_page, write_page
from .wiki import read_optional, slugify, today


@dataclass
class QueryResult:
    answer: str
    pages_used: list[str] = field(default_factory=list)
    saved_path: Path | None = None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _build_context(config: Config, question: str, course: str | None, top_k: int):
    hits = search(config, question, page_type="concept", top_k=top_k, course=course)
    blocks: list[str] = []
    used: list[str] = []
    total = 0
    for hit in hits:
        page = read_page(hit.ref.path)
        if page is None:
            continue
        block = (
            f"### [[{hit.ref.slug}]] — {hit.ref.title} (course: {hit.ref.course})\n"
            f"{page.content}"
        )
        tokens = _estimate_tokens(block)
        if total + tokens > config.context_token_budget and blocks:
            break
        blocks.append(block)
        used.append(hit.ref.slug)
        total += tokens
    return blocks, used


def answer(
    config: Config,
    provider: LLMProvider,
    question: str,
    *,
    course: str | None = None,
    top_k: int | None = None,
    save: bool = False,
) -> QueryResult:
    top_k = top_k or config.search_top_k
    blocks, used = _build_context(config, question, course, top_k)
    context = "\n\n".join(blocks) or "(no matching pages found)"

    system = "\n\n".join(
        p
        for p in (
            prompts.load("answer.md"),
            read_optional(config.purpose_file),
            read_optional(config.schema_file),
        )
        if p.strip()
    ).strip()
    user = f"Question: {question}\n\nWiki pages:\n\n{context}"

    text = provider.complete(system, user)

    saved: Path | None = None
    if save:
        slug = slugify(question)[:60] or "query"
        saved = config.queries_dir / f"{slug}.md"
        metadata = {
            "title": question,
            "type": "query",
            "course": course or config.default_course,
            "created": today(),
        }
        write_page(saved, metadata, text.strip() + "\n")

    return QueryResult(answer=text, pages_used=used, saved_path=saved)
