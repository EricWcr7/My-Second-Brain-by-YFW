"""Source loaders: normalize any supported source into Markdown."""

from __future__ import annotations

from .base import LoaderError, LoadResult
from .registry import is_url, load_source

__all__ = ["LoaderError", "LoadResult", "is_url", "load_source"]
