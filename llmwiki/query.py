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


_FORMAT_DIRECTIVES = {
    "table": (
        "Output format: present the answer as a Markdown **comparison table** "
        "wherever a table aids clarity (one row per item, columns for the "
        "dimensions compared). Keep the inline `[[slug]]` citations and the final "
        "**Sources** list."
    ),
    "slides": (
        "Output format: present the answer as a **Marp**-style slide deck — one "
        "slide per key point, with slides separated by a line containing only "
        "`---`. Start with a short title slide. Keep the inline `[[slug]]` "
        "citations and end with a **Sources** slide. Do not add a YAML "
        "front-matter block; it is added automatically when the deck is saved."
    ),
}


def _format_directive(fmt: str) -> str:
    """Extra system-prompt instruction for a non-prose answer format."""
    return _FORMAT_DIRECTIVES.get(fmt, "")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _build_context(config: Config, question: str, section: str | None, top_k: int):
    hits = search(config, question, page_type="concept", top_k=top_k, section=section)
    blocks: list[str] = []
    used: list[str] = []
    total = 0
    for hit in hits:
        page = read_page(hit.ref.path)
        if page is None:
            continue
        block = (
            f"### [[{hit.ref.slug}]] — {hit.ref.title} (section: {hit.ref.section or 'General'})\n"
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
    section: str | None = None,
    top_k: int | None = None,
    save: bool = False,
    fmt: str = "prose",
) -> QueryResult:
    top_k = top_k or config.search_top_k
    blocks, used = _build_context(config, question, section, top_k)
    context = "\n\n".join(blocks) or "(no matching pages found)"

    system = "\n\n".join(
        p
        for p in (
            prompts.load("answer.md"),
            _format_directive(fmt),
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
            "section": section if section is not None else config.default_section,
            "created": today(),
        }
        if fmt == "slides":
            metadata["marp"] = True  # Obsidian Marp plugin renders the saved deck
        write_page(saved, metadata, text.strip() + "\n")

    return QueryResult(answer=text, pages_used=used, saved_path=saved)
