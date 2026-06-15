"""Markdown / plain-text loader: passthrough."""

from __future__ import annotations

from pathlib import Path

from .base import LoaderError, LoadResult, title_from_markdown


def load(path: Path, **_kwargs) -> LoadResult:
    try:
        text = path.read_text("utf-8")
    except UnicodeDecodeError:
        text = path.read_text("utf-8", errors="replace")
    except OSError as e:
        raise LoaderError(f"Could not read {path}: {e}") from e
    kind = "markdown" if path.suffix.lower() in (".md", ".markdown") else "text"
    return LoadResult(markdown=text, kind=kind, title=title_from_markdown(text, path.stem))
