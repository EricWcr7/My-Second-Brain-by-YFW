"""Loader result type and shared helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


class LoaderError(Exception):
    """Raised when a source cannot be loaded or normalized."""


@dataclass
class LoadResult:
    markdown: str  # normalized Markdown content
    kind: str  # markdown|text|pdf|docx|pptx|image|web
    title: str  # human-readable title guess


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def title_from_markdown(markdown: str, fallback: str) -> str:
    """Use the first level-1 heading as the title, else the fallback."""
    match = _H1_RE.search(markdown)
    if match:
        return match.group(1).strip()
    return fallback
