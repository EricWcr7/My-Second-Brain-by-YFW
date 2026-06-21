"""Split a wiki page into retrieval chunks (pure, deterministic — no LLM).

The wiki is already concept-granular (one concept per page), but a page can still
carry several sub-ideas under different headings. Chunking embeds each heading
section separately so a query about one sub-part matches sharply; the search layer
then aggregates chunk hits back to their parent page, so the ``[[slug]]`` citation
and grounding contract stays page-level.

Splitting is heading-first (``##``/``###``); a section longer than
``chunk_max_chars`` is sub-split on blank-line (paragraph) boundaries with greedy
packing. Display math (``$$…$$``) is never split: a flush is held until the
accumulated text has balanced ``$$`` fences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .store import sha256_bytes
from .wiki import PageRef

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    id: str  # f"{page_slug}#{i}"
    page_slug: str
    section: str
    page_title: str
    heading: str  # the ##/### heading text; "" for the pre-heading lede
    text: str  # the chunk body (heading line included so it reads naturally)
    content_hash: str  # sha256 of embed_text(); drives incremental re-embed

    def embed_text(self) -> str:
        """The exact string sent to the embedding model (page title for context)."""
        return f"{self.page_title}\n\n{self.text}".strip()


def _split_by_heading(content: str) -> list[tuple[str, str]]:
    """Split a page body into ``(heading, block_text)`` pairs at ##/### headings.

    Text before the first heading becomes a ``("", lede)`` pair. ``block_text``
    keeps the heading line so the chunk reads naturally and embeds with context.
    """
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in content.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            sections.append((m.group(2).strip(), [line]))
        else:
            sections[-1][1].append(line)
    out: list[tuple[str, str]] = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if text:
            out.append((heading, text))
    return out


def _balanced_math(text: str) -> bool:
    """True if ``$$`` display-math fences are balanced (even count)."""
    return text.count("$$") % 2 == 0


def _subsplit(text: str, max_chars: int) -> list[str]:
    """Greedily pack paragraphs into <= max_chars chunks, never splitting math."""
    paras = [p for p in _PARA_SPLIT_RE.split(text) if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    for para in paras:
        cur.append(para)
        joined = "\n\n".join(cur)
        if len(joined) >= max_chars and _balanced_math(joined):
            chunks.append(joined)
            cur = []
    if cur:
        joined = "\n\n".join(cur)
        # A dangling tail with unbalanced fences (very rare) folds into the last
        # chunk rather than being emitted mid-math.
        if chunks and not _balanced_math(joined):
            chunks[-1] = chunks[-1] + "\n\n" + joined
        else:
            chunks.append(joined)
    return chunks or [text]


def chunk_page(ref: PageRef, content: str, *, max_chars: int) -> list[Chunk]:
    """Split ``content`` into ordered chunks carrying ``ref``'s page metadata."""
    chunks: list[Chunk] = []
    for heading, block in _split_by_heading(content):
        pieces = [block] if len(block) <= max_chars else _subsplit(block, max_chars)
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            chunk = Chunk(
                id=f"{ref.slug}#{len(chunks)}",
                page_slug=ref.slug,
                section=ref.section,
                page_title=ref.title,
                heading=heading,
                text=piece,
                content_hash="",
            )
            chunk.content_hash = sha256_bytes(chunk.embed_text().encode("utf-8"))
            chunks.append(chunk)
    return chunks
