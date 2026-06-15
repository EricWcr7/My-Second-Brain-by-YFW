"""Wiki conventions: slugs, wikilinks, page paths, and the index/log surfaces.

The wiki is concept-centric and Obsidian-compatible:
- one page per concept under ``wiki/concepts/<course>/``
- one page per source under ``wiki/sources/<course>/``
- ``index.md`` is regenerated deterministically from disk after each change
- ``log.md`` is an append-only operation record
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


def course_slug(course: str) -> str:
    return slugify(course)


def strip_wikilink_target(link: str) -> str:
    """``slug|Alias`` or ``slug#Heading`` -> ``slug``."""
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def extract_wikilinks(text: str) -> set[str]:
    return {strip_wikilink_target(m.group(1)) for m in WIKILINK_RE.finditer(text)}


def concept_path(config: Config, course: str, title: str) -> Path:
    return config.concepts_dir / course_slug(course) / f"{slugify(title)}.md"


def source_path(config: Config, course: str, source_slug: str) -> Path:
    return config.source_pages_dir / course_slug(course) / f"{source_slug}.md"


def today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class PageRef:
    slug: str
    title: str
    course: str
    page_type: str  # "concept" | "source"
    path: Path


def iter_pages(config: Config, page_type: str) -> list[PageRef]:
    """List concept or source pages with their slugs/titles/courses."""
    base = config.concepts_dir if page_type == "concept" else config.source_pages_dir
    refs: list[PageRef] = []
    if not base.exists():
        return refs
    for path in sorted(base.rglob("*.md")):
        page = read_page(path)
        if page is None:
            continue
        course = str(page.metadata.get("course", "")) or path.parent.name
        title = str(page.metadata.get("title", path.stem))
        refs.append(
            PageRef(
                slug=path.stem,
                title=title,
                course=course,
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
    """Regenerate ``index.md`` from the pages currently on disk."""
    concepts = iter_pages(config, "concept")
    sources = iter_pages(config, "source")

    courses = sorted({r.course for r in concepts} | {r.course for r in sources})
    lines = [
        "# Index",
        "",
        "Navigation catalog for the wiki. Regenerated automatically by llmwiki.",
        "",
        f"_Concepts: {len(concepts)} · Sources: {len(sources)} · "
        f"Courses: {len(courses)}_",
        "",
    ]
    if not courses:
        lines.append("_No pages yet. Run `llmwiki ingest <path|url>`._")

    for course in courses:
        lines.append(f"## {course}")
        lines.append("")
        c_here = sorted(
            (r for r in concepts if r.course == course), key=lambda r: r.title.lower()
        )
        s_here = sorted(
            (r for r in sources if r.course == course), key=lambda r: r.title.lower()
        )
        lines.append("### Concepts")
        if c_here:
            lines += [f"- [[{r.slug}|{r.title}]]" for r in c_here]
        else:
            lines.append("_none yet_")
        lines.append("")
        lines.append("### Sources")
        if s_here:
            lines += [f"- [[{r.slug}|{r.title}]]" for r in s_here]
        else:
            lines.append("_none yet_")
        lines.append("")

    ensure_dir(config.wiki_dir)
    config.index_file.write_text("\n".join(lines).rstrip() + "\n", "utf-8")


def read_optional(path: Path) -> str:
    return path.read_text("utf-8") if path.exists() else ""
