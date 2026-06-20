"""Query pipeline: keyword-retrieve wiki pages, then answer with citations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import overrides
from .config import Config
from .providers.base import LLMProvider
from .search import search
from .store import read_page, write_page
from .wiki import all_concept_slugs, extract_wikilinks, iter_pages, slugify, today


@dataclass
class QueryResult:
    answer: str
    pages_used: list[str] = field(default_factory=list)
    # Slugs the answer cited with `[[slug]]` that match no wiki page — i.e. the
    # model invented a citation. The grounding check surfaces these so a reader
    # (web Ask / CLI) can distrust them instead of taking provenance on faith.
    ungrounded: list[str] = field(default_factory=list)
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
    attachments: list[tuple[str, str]] | None = None,
) -> QueryResult:
    top_k = top_k or config.search_top_k
    blocks, _retrieved = _build_context(config, question, section, top_k)
    context = "\n\n".join(blocks) or "(no matching pages found)"

    system = "\n\n".join(
        p
        for p in (
            overrides.effective(config, section, "answer"),
            _format_directive(fmt),
            overrides.effective(config, section, "purpose"),
            overrides.effective(config, section, "schema"),
        )
        if p.strip()
    ).strip()
    user = f"Question: {question}\n\nWiki pages:\n\n{context}"

    # Attachments are transient context supplied with the question (e.g. an
    # uploaded file in the web UI). They are not wiki pages, so they aren't cited.
    if attachments:
        attached = "\n\n".join(
            f"--- ATTACHED FILE: {name} ---\n{md}" for name, md in attachments
        )
        user += f"\n\nAttached files (additional context):\n\n{attached}"

    text = provider.complete(system, user)

    # Grounding check: every `[[slug]]` the answer cites must resolve to a real
    # wiki page. Citations that don't (the model invented them) are reported as
    # `ungrounded`; the ones that do become the answer's pages_used. This is the
    # programmatic enforcement of the wiki's provenance contract — the model is
    # *told* not to invent citations (answer.md), and here we verify it.
    existing = all_concept_slugs(config) | {ref.slug for ref in iter_pages(config, "source")}
    cited = extract_wikilinks(text)
    pages_used = sorted(s for s in cited if s in existing)
    ungrounded = sorted(s for s in cited if s not in existing)

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

    return QueryResult(
        answer=text, pages_used=pages_used, ungrounded=ungrounded, saved_path=saved
    )
