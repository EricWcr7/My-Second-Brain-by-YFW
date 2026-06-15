"""Prompt templates packaged with llmwiki."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load(name: str) -> str:
    """Load a prompt template by filename (e.g. ``answer.md``)."""
    return (_DIR / name).read_text("utf-8")
