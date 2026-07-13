"""Provider-agnostic LLM interface.

Keeping this thin lets the backend (OpenAI or Anthropic) be swapped via config
without touching the ingest/query/lint pipelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderError(Exception):
    """Raised on provider configuration or response failures."""


@dataclass
class Usage:
    """Token accounting for the most recent provider call (None if unknown)."""

    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class ChatAttachment:
    """A file sent natively with a chat message (raw bytes, not transcribed)."""

    path: Path  # persisted bytes on disk; the caller owns the file's lifetime
    name: str  # original filename
    kind: str  # "pdf" | "image"


@dataclass
class ChatMessage:
    """One turn of a multi-turn conversation."""

    role: str  # "user" | "assistant"
    text: str
    attachments: list[ChatAttachment] = field(default_factory=list)  # user turns only


class LLMProvider(ABC):
    # Token usage from the last call, for observability. Concrete providers set
    # this; the base default keeps fakes and key-less paths safe to read.
    last_usage: Usage | None = None

    def with_timeout(self, timeout: float) -> "LLMProvider":
        """Return a view of this provider whose calls use ``timeout`` seconds.

        Ingest wraps its provider with a longer timeout than the interactive
        query/lint path (a big source runs many slow model passes). The default
        is a no-op so fakes and key-less paths stay safe; SDK-backed providers
        override it to scope the underlying client's per-request timeout.
        """
        return self

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
    def chat(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int = 16000,
        effort: str | None = None,
    ) -> str:
        """Multi-turn completion over ``messages`` (oldest first, ending on a
        user turn). Attachments are sent natively as document/image blocks,
        never transcribed. ``effort`` requests a reasoning effort where the
        backend supports it (OpenAI ``reasoning.effort``); backends without an
        equivalent knob ignore it."""

    @abstractmethod
    def transcribe_pdf(self, path: Path) -> str:
        """Transcribe a PDF (incl. scanned/math pages) to faithful Markdown."""

    @abstractmethod
    def transcribe_image(self, path: Path) -> str:
        """Transcribe an image to faithful Markdown."""

    @abstractmethod
    def count_tokens(self, system: str, user: str, *, model: str | None = None) -> int:
        """Count input tokens for a prospective request."""
