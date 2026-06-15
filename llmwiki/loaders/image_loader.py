"""Image loader: vision transcription to Markdown."""

from __future__ import annotations

from pathlib import Path

from ..providers.base import LLMProvider
from .base import LoaderError, LoadResult


def load(path: Path, *, provider: LLMProvider, **_kwargs) -> LoadResult:
    markdown = provider.transcribe_image(path)
    if not markdown.strip():
        raise LoaderError(f"Vision transcription produced no text for {path}.")
    return LoadResult(markdown=markdown, kind="image", title=path.stem)
