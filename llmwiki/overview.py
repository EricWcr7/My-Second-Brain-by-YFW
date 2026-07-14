"""Section overviews: an LLM-maintained narrative orientation per section.

Every section (the General root, branches, and courses/sub-sections) carries an
overview — a high-level map of what it covers and how the ideas connect. Unlike
``index.md`` (a deterministic catalog), an overview is *generated*: the model is
fed a compact catalog of the section's concept pages and writes prose that links
them with ``[[slug]]``.

The pass mirrors :func:`llmwiki.query.answer` — assemble ``overview`` prompt +
purpose + schema, call ``provider.complete``, then write the file
**deterministically** (LLM call and file IO kept separate). Overviews refresh on
ingest (the target section and its ancestors) and on demand; storage lives at
``wiki.overview_path`` (the General root reuses ``wiki/overview.md``).
"""

from __future__ import annotations

from pathlib import Path

from . import overrides, prompts
from .config import Config
from .providers.base import LLMProvider
from .store import ensure_dir, read_page
from .wiki import (
    iter_pages,
    normalize_section,
    overview_path,
    section_contains,
)

# Same rough chars-per-token estimate the query pipeline uses to budget context.
_CHARS_PER_TOKEN = 4
_SUMMARY_MAX_CHARS = 200


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _first_line(body: str) -> str:
    """The first non-empty, non-heading line of a page body (a 1-line gist)."""
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s[:_SUMMARY_MAX_CHARS]
    return ""


def build_overview_input(config: Config, section: str) -> tuple[str, list[str]]:
    """Compact catalog of the concept pages in ``section`` and its descendants.

    Returns ``(catalog_markdown, slugs)``: the catalog groups pages by their own
    (sub-)section and lists ``- [[slug]] — title`` lines (with tags and a 1-line
    gist while within ``context_token_budget``, so even a General-scope refresh
    stays cheap); ``slugs`` is the set the overview is allowed to link.
    """
    refs = [r for r in iter_pages(config, "concept") if section_contains(section, r.section)]
    refs.sort(key=lambda r: (r.section, r.title.lower()))
    slugs = [r.slug for r in refs]
    if not refs:
        return "(no concept pages in this section yet)", slugs

    budget = config.context_token_budget
    total = 0
    lines: list[str] = []
    current: str | None = None
    for r in refs:
        if r.section != current:
            current = r.section
            header = f"## {r.section or 'General'}"
            lines.append(header)
            total += _estimate_tokens(header)
        line = f"- [[{r.slug}]] — {r.title}"
        # Enrich with tags + a gist only while under budget; titles always listed.
        if total <= budget:
            page = read_page(r.path)
            if page is not None:
                tags = [str(t) for t in (page.metadata.get("tags") or []) if str(t).strip()]
                if tags:
                    line += f" (tags: {', '.join(tags)})"
                gist = _first_line(page.content)
                if gist:
                    line += f" — {gist}"
        lines.append(line)
        total += _estimate_tokens(line)
    return "\n".join(lines), slugs


def refresh_overview(config: Config, provider: LLMProvider, section: str) -> Path:
    """(Re)generate the overview for ``section`` and write it to disk.

    An empty section gets a short deterministic stub (no model call); otherwise the
    model writes a narrative grounded in the section's concept catalog, linking
    only the catalog's slugs. Returns the path written.
    """
    section = normalize_section(section)
    path = overview_path(config, section)
    catalog, slugs = build_overview_input(config, section)
    label = section.split("/")[-1] if section else "General"

    if not slugs:
        ensure_dir(path.parent)
        path.write_text(
            f"# {label} — overview\n\n"
            "_No pages in this section yet. Ingest a source to build the overview._\n",
            "utf-8",
        )
        return path

    system = "\n\n".join(
        p
        for p in (
            prompts.load("overview.md"),
            overrides.effective(config, section, "purpose"),
            overrides.effective(config, section, "schema"),
        )
        if p.strip()
    ).strip()
    allowed = ", ".join(f"[[{s}]]" for s in slugs)
    user = (
        f"Section: {section or 'General'}\n\n"
        f"Link only these concept slugs (use only the ones you reference):\n{allowed}\n\n"
        f"Concept catalog (grouped by sub-section):\n\n{catalog}\n"
    )
    text = provider.complete(system, user)
    ensure_dir(path.parent)
    path.write_text(text.strip() + "\n", "utf-8")
    return path
