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
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .store import Page, ensure_dir, load_state, read_page, save_state
from .vectorindex import VectorIndexUnavailable, open_index

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def slugify(text: str) -> str:
    """Lowercase, ASCII, hyphen-separated slug used for filenames and links."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "untitled"


def section_slug(text: str) -> str:
    """Folder/slug for a section segment: case- and Unicode-preserving.

    Keeps CJK and other letters/digits; collapses runs of whitespace/punctuation
    to hyphens. Unlike :func:`slugify` (used for page filenames and wikilinks),
    this is NOT lowercased or ASCII-folded, so course codes like ``example-course`` keep
    their casing and names like ``线性代数`` survive instead of becoming ``untitled``.
    """
    text = unicodedata.normalize("NFKC", text).strip()
    text = re.sub(r"[^\w]+", "-", text, flags=re.UNICODE)  # \w is Unicode-aware
    return text.strip("-_") or "untitled"


def section_segments(section: str) -> list[str]:
    """Split a section path into its non-empty slug segments."""
    return [seg for seg in (section or "").split("/") if seg]


def section_to_relpath(section: str) -> Path:
    """Turn a section path into a slugified, nested relative directory."""
    return Path(*[section_slug(seg) for seg in section_segments(section)])


def normalize_section(section: str) -> str:
    """Canonical ``/``-joined form of a section path (slugified segments)."""
    return "/".join(section_slug(seg) for seg in section_segments(section))


def section_ancestry(section: str) -> list[str]:
    """The General root down to ``section``: ``["", …parents…, section]``.

    e.g. ``"academic/example-course"`` -> ``["", "academic", "academic/example-course"]``.
    Mirrors the frontend ``sectionAncestors``; used to refresh a section's
    overview together with every ancestor that summarizes it.
    """
    segs = section_segments(normalize_section(section))
    return [""] + ["/".join(segs[: i + 1]) for i in range(len(segs))]


def section_dirs(config: Config) -> set[str]:
    """Normalized section paths that exist as directories under concepts/ or sources/.

    Sections are folders, so a branch/course is real as soon as its directory
    exists — even before any page is filed there. Listing them (not just pages)
    lets the seeded ``academic``/``non-academic`` branches and freshly-created
    courses appear in the UI and persist across restarts.
    """
    out: set[str] = set()
    for base in (config.concepts_dir, config.source_pages_dir):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_dir():
                out.add(normalize_section("/".join(path.relative_to(base).parts)))
    out.discard("")
    return out


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


def overview_path(config: Config, section: str) -> Path:
    """Where a section's overview lives.

    The General root (``""``) reuses ``wiki/overview.md`` (already wired to the
    home view); every other section maps to ``overviews/<section-relpath>.md``.
    Overviews sit OUTSIDE ``concepts/``/``sources/`` so ``iter_pages`` never sees
    them as wiki pages.
    """
    if not normalize_section(section):
        return config.overview_file
    return config.overviews_dir / section_to_relpath(section).with_suffix(".md")


def today() -> str:
    return _dt.date.today().isoformat()


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


LOG_HEADER = (
    "# Log\n\n"
    "Chronological record of wiki operations. Each entry begins with a\n"
    "`## [YYYY-MM-DD] <op> | <title>` heading so the timeline is greppable\n"
    "(e.g. `grep '^## \\[' log.md | tail -5`).\n\n"
)


def append_log(config: Config, op: str, title: str, *, detail: str = "") -> None:
    """Append a greppable operation entry to ``log.md``.

    Writes a ``## [YYYY-MM-DD] <op> | <title>`` heading (so the timeline can be
    sliced by grepping the ``## [`` prefix), optionally followed by a one-line
    detail.
    """
    ensure_dir(config.wiki_dir)
    block = f"## [{today()}] {op} | {title.strip()}\n"
    if detail.strip():
        block += f"{detail.strip()}\n"
    block += "\n"
    if config.log_file.exists():
        with open(config.log_file, "a", encoding="utf-8") as f:
            f.write(block)
    else:
        config.log_file.write_text(LOG_HEADER + block, "utf-8")


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


def _section_owns(scope: str, candidate: str) -> bool:
    """True if ``candidate`` is ``scope`` or a section nested under it.

    Case-insensitive (course casing drifts between deletes/recreates) and, unlike
    :func:`section_contains`, an empty ``scope`` owns *nothing* — purging the
    General root must never sweep every record.
    """
    s = normalize_section(scope).lower()
    c = normalize_section(candidate).lower()
    return bool(s) and (c == s or c.startswith(s + "/"))


def purge_section(config: Config, section: str) -> list[str]:
    """Tear a section down *completely*; return the ledger keys removed.

    Deleting a section must leave nothing behind. Removing only the page
    directories (the old behavior) stranded three kinds of artifact, so a later
    re-ingest of the same file was silently skipped as "unchanged" and orphans
    piled up:

    1. the ``state.json`` ledger record for each source filed there — dropped
       here along with the bytes it owns: the ``normalized/<checksum>.md`` cache
       and the ``raw/`` file;
    2. the concept/source page subtrees, plus the section's own overview page
       and its descendants' overviews under ``wiki/overviews/``;
    3. the per-section override files under ``.llmwiki/sections/``;
    4. the deleted concepts' chunks in the vector index (so semantic search can't
       still surface a page that no longer exists).

    The match covers descendant sections, so deleting a branch clears every
    course beneath it. Assets attached to image sources are not ledger-tracked
    and are out of scope. Index/log writes stay with the pipeline: this refreshes
    ``index.md``; callers append their own ``log.md`` entry.
    """
    rel = section_to_relpath(section)
    # Capture the concept slugs before the pages are gone, so their vectors can be
    # dropped from the index afterwards.
    doomed_slugs = {
        ref.slug
        for ref in iter_pages(config, "concept")
        if _section_owns(section, ref.section)
    }

    state = load_state(config)
    sources = state.get("sources", {})
    removed = [
        key
        for key, rec in sources.items()
        if _section_owns(section, str(rec.get("section", "")))
    ]
    for key in removed:
        rec = sources.pop(key)
        checksum = rec.get("checksum")
        if checksum:
            (config.normalized_dir / f"{checksum}.md").unlink(missing_ok=True)
        raw_ref = rec.get("raw_ref")
        if raw_ref:
            (config.root / raw_ref).unlink(missing_ok=True)
    if removed:
        save_state(config, state)

    for base in (
        config.concepts_dir,
        config.source_pages_dir,
        config.section_overrides_dir,
        config.overviews_dir,  # the descendants' overview subtree
    ):
        target = base / rel
        if target.exists():
            shutil.rmtree(target)
    # The section's own overview is a FILE (``overviews/<rel>.md``), removed
    # separately from the descendants subtree swept above.
    overview_path(config, section).unlink(missing_ok=True)

    rebuild_index(config)  # drop the deleted pages from index.md

    if doomed_slugs:
        # Best-effort: a missing search extra / index just means nothing to drop.
        try:
            open_index(config).delete_page_slugs(doomed_slugs)
        except VectorIndexUnavailable:
            pass
        except Exception:  # pragma: no cover - resilience path; never block a delete
            pass

    return removed


def read_optional(path: Path) -> str:
    return path.read_text("utf-8") if path.exists() else ""
