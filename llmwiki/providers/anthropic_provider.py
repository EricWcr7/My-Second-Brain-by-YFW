"""Claude (Anthropic) implementation of :class:`LLMProvider`.

Uses the official ``anthropic`` SDK. The API key is read from the environment
(``ANTHROPIC_API_KEY``). Compilation/answering runs on Opus 4.8 with adaptive
thinking; the stable system prompt is prompt-cached.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from ..config import Config
from .base import LLMProvider, ProviderError, T

TRANSCRIBE_INSTRUCTION = (
    "Transcribe this document into clean, faithful Markdown for an academic study "
    "wiki. Preserve ALL mathematics as LaTeX (inline `$...$`, display `$$...$$`) "
    "using the notation in the source. Keep definitions, theorems, assumptions, "
    "proofs, and examples intact and in order. Describe figures/diagrams briefly "
    "in text. Do not summarize or omit content. Output only the Markdown."
)


def _text_of(message) -> str:
    return "".join(b.text for b in message.content if b.type == "text").strip()


class AnthropicProvider(LLMProvider):
    DEFAULT_COMPILE_MODEL = "claude-opus-4-8"
    DEFAULT_CHEAP_MODEL = "claude-haiku-4-5"

    def __init__(self, config: Config):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - import guard
            raise ProviderError(
                "The `anthropic` package is required. Install with `pip install anthropic`."
            ) from e
        self.config = config
        self.compile_model = config.compile_model or self.DEFAULT_COMPILE_MODEL
        self.cheap_model = config.cheap_model or self.DEFAULT_CHEAP_MODEL
        self._anthropic = anthropic
        try:
            self.client = anthropic.Anthropic()
        except Exception as e:  # missing key etc.
            raise ProviderError(
                "Could not initialize the Anthropic client. Set ANTHROPIC_API_KEY."
            ) from e

    def _system_blocks(self, system: str) -> list[dict]:
        # Cache the stable system prefix across ingests/queries.
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def complete(
        self, system: str, user: str, *, model: str | None = None, max_tokens: int = 16000
    ) -> str:
        model = model or self.compile_model
        with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=self._system_blocks(system),
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
        return _text_of(message)

    def parse(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> T:
        model = model or self.compile_model
        response = self.client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=self._system_blocks(system),
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if response.parsed_output is None:
            reason = getattr(response, "stop_reason", "unknown")
            raise ProviderError(f"Structured parse returned no output (stop_reason={reason}).")
        return response.parsed_output

    def transcribe_pdf(self, path: Path) -> str:
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        with self.client.messages.stream(
            model=self.compile_model,
            max_tokens=16000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": data,
                            },
                        },
                        {"type": "text", "text": TRANSCRIBE_INSTRUCTION},
                    ],
                }
            ],
        ) as stream:
            message = stream.get_final_message()
        return _text_of(message)

    def transcribe_image(self, path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        with self.client.messages.stream(
            model=self.compile_model,
            max_tokens=8000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data,
                            },
                        },
                        {"type": "text", "text": TRANSCRIBE_INSTRUCTION},
                    ],
                }
            ],
        ) as stream:
            message = stream.get_final_message()
        return _text_of(message)

    def count_tokens(self, system: str, user: str, *, model: str | None = None) -> int:
        model = model or self.compile_model
        result = self.client.messages.count_tokens(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return result.input_tokens
