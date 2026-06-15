"""Wiki conventions: slugs, wikilinks, page paths, and the index/log surfaces.

The wiki is concept-centric and Obsidian-compatible:
- one page per concept under ``wiki/concepts/<section>/``
- one page per source under ``wiki/sources/<section>/``
- ``index.md`` is regenerated deterministically from disk after each change
- ``log.md`` is an append-only operation record

A *section* is the page's folder path under ``concepts/``/``sources/``, stored as a
``/``-joined string of slug segments (e.g. ``"academic/multivariable-calculus"``).
The empty string ``""`` is the General root. Scope access is a prefix test: a scope
sees a page iff the scope is a prefix of the page's section (see ``section_contains``).
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .store import Page, ensure_dir, read_page

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def slugify(text: str) -> str:
    """Lowercase, ASCII, hyphen-separated slug used for filenames and links."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "untitled"


def section_segments(section: str) -> list[str]:
    """Split a section path into its non-empty slug segments."""
    return [seg for seg in (section or "").split("/") if seg]


def section_to_relpath(section: str) -> Path:
    """Turn a section path into a slugified, nested relative directory."""
    return Path(*[slugify(seg) for seg in section_segments(section)])


def normalize_section(section: str) -> str:
    """Canonical ``/``-joined form of a section path (slugified segments)."""
    return "/".join(slugify(seg) for seg in section_segments(section))


def section_contains(scope: str, section: str) -> bool:
    """True if ``scope`` can access ``section`` — i.e. scope is a prefix of it.

    The General root (``scope == ""``) sees everything; a branch like ``"academic"``
    sees all its courses; a leaf course sees only itself. Matching is on segment
    boundaries so ``"academic"`` does not match ``"academic-archive"``.
    """
    scope = normalize_section(scope)
    section = normalize_section(section)
    return scope == "" or section == scope or section.startswith(scope + "/")


def strip_wikilink_target(link: str) -> str:
    """``slug|Alias`` or ``slug#Heading`` -> ``slug``."""
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def extract_wikilinks(text: str) -> set[str]:
    return {strip_wikilink_target(m.group(1)) for m in WIKILINK_RE.finditer(text)}


def concept_path(config: Config, section: str, title: str) -> Path:
    return config.concepts_dir / section_to_relpath(section) / f"{slugify(title)}.md"


def source_path(config: Config, section: str, source_slug: str) -> Path:
    return config.source_pages_dir / section_to_relpath(section) / f"{source_slug}.md"


def today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class PageRef:
    slug: str
    title: str
    section: str
    page_type: str  # "concept" | "source"
    path: Path


def iter_pages(config: Config, page_type: str) -> list[PageRef]:
    """List concept or source pages with their slugs/titles/sections."""
    base = config.concepts_dir if page_type == "concept" else config.source_pages_dir
    refs: list[PageRef] = []
    if not base.exists():
        return refs
    for path in sorted(base.rglob("*.md")):
        page = read_page(path)
        if page is None:
            continue
        # Section is the folder path under base/ (frontmatter may override it).
        folder = "/".join(path.relative_to(base).parent.parts)
        section = normalize_section(str(page.metadata.get("section", "")) or folder)
        title = str(page.metadata.get("title", path.stem))
        refs.append(
            PageRef(
                slug=path.stem,
                title=title,
                section=section,
                page_type=page_type,
                path=path,
            )
        )
    return refs


def all_concept_slugs(config: Config) -> set[str]:
    return {ref.slug for ref in iter_pages(config, "concept")}


def append_log(config: Config, entry: str) -> None:
    ensure_dir(config.wiki_dir)
    line = f"- {_now()} — {entry.strip()}\n"
    if config.log_file.exists():
        with open(config.log_file, "a", encoding="utf-8") as f:
            f.write(line)
    else:
        config.log_file.write_text(
            f"# Log\n\nChronological record of wiki operations.\n\n{line}", "utf-8"
        )


def rebuild_index(config: Config) -> None:
    """Regenerate ``index.md`` from the pages currently on disk.

    Pages are grouped by section; heading depth mirrors the section's depth so the
    catalog reads as the General → branch → course hierarchy.
    """
    concepts = iter_pages(config, "concept")
    sources = iter_pages(config, "source")

    sections = sorted({r.section for r in concepts} | {r.section for r in sources})
    lines = [
        "# Index",
        "",
        "Navigation catalog for the wiki. Regenerated automatically by llmwiki.",
        "",
        f"_Concepts: {len(concepts)} · Sources: {len(sources)} · "
        f"Sections: {len(sections)}_",
        "",
    ]
    if not sections:
        lines.append("_No pages yet. Run `llmwiki ingest <path|url>`._")

    for section in sections:
        depth = len(section_segments(section))
        heading = "#" * min(depth + 2, 6)
        lines.append(f"{heading} {section or 'General'}")
        lines.append("")
        c_here = sorted(
            (r for r in concepts if r.section == section), key=lambda r: r.title.lower()
        )
        s_here = sorted(
            (r for r in sources if r.section == section), key=lambda r: r.title.lower()
        )
        if c_here:
            lines += [f"- [[{r.slug}|{r.title}]]" for r in c_here]
        if s_here:
            lines += [f"- [[{r.slug}|{r.title}]] _(source)_" for r in s_here]
        if not c_here and not s_here:
            lines.append("_none yet_")
        lines.append("")

    ensure_dir(config.wiki_dir)
    config.index_file.write_text("\n".join(lines).rstrip() + "\n", "utf-8")


def read_optional(path: Path) -> str:
    return path.read_text("utf-8") if path.exists() else ""
