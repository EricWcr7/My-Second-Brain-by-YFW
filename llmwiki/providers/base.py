"""Provider-agnostic LLM interface.

Keeping this thin lets the backend (OpenAI or Anthropic) be swapped via config
without touching the ingest/query/lint pipelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderError(Exception):
    """Raised on provider configuration or response failures."""


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self, system: str, user: str, *, model: str | None = None, max_tokens: int = 16000
    ) -> str:
        """Return the model's text answer (free-form Markdown)."""

    @abstractmethod
    def parse(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> T:
        """Return a validated instance of ``schema`` (structured output)."""

    @abstractmethod
    def transcribe_pdf(self, path: Path) -> str:
        """Transcribe a PDF (incl. scanned/math pages) to faithful Markdown."""

    @abstractmethod
    def transcribe_image(self, path: Path) -> str:
        """Transcribe an image to faithful Markdown."""

    @abstractmethod
    def count_tokens(self, system: str, user: str, *, model: str | None = None) -> int:
        """Count input tokens for a prospective request."""
