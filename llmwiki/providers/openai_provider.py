"""OpenAI implementation of :class:`LLMProvider`.

Uses the official ``openai`` SDK and its Responses API. The API key is read from
the environment (``OPENAI_API_KEY``). This is the default backend; switch to
Claude by setting ``provider = "anthropic"`` in ``.llmwiki/config.toml``.

Every operation runs on a GPT-5.5+ reasoning model at ``xhigh`` reasoning effort.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from ..config import Config
from .base import LLMProvider, ProviderError, T

# Reasoning effort applied to every call. xhigh is supported on gpt-5.5+.
REASONING_EFFORT = "xhigh"
# Reasoning tokens count toward ``max_output_tokens``; reserve headroom on top of
# the caller's output budget so xhigh reasoning can't starve the visible answer.
REASONING_TOKEN_RESERVE = 25_000

TRANSCRIBE_INSTRUCTION = (
    "Transcribe this document into clean, faithful Markdown for an academic study "
    "wiki. Preserve ALL mathematics as LaTeX (inline `$...$`, display `$$...$$`) "
    "using the notation in the source. Keep definitions, theorems, assumptions, "
    "proofs, and examples intact and in order. Describe figures/diagrams briefly "
    "in text. Do not summarize or omit content. Output only the Markdown."
)


class OpenAIProvider(LLMProvider):
    DEFAULT_COMPILE_MODEL = "gpt-5.5"
    DEFAULT_CHEAP_MODEL = "gpt-5.5"

    def __init__(self, config: Config):
        try:
            import openai
        except ImportError as e:  # pragma: no cover - import guard
            raise ProviderError(
                "The `openai` package is required. Install with `pip install openai`."
            ) from e
        self.config = config
        self.compile_model = config.compile_model or self.DEFAULT_COMPILE_MODEL
        self.cheap_model = config.cheap_model or self.DEFAULT_CHEAP_MODEL
        self._openai = openai
        try:
            self.client = openai.OpenAI()
        except Exception as e:  # missing key etc.
            raise ProviderError(
                "Could not initialize the OpenAI client. Set OPENAI_API_KEY."
            ) from e

    def complete(
        self, system: str, user: str, *, model: str | None = None, max_tokens: int = 16000
    ) -> str:
        response = self.client.responses.create(
            model=model or self.compile_model,
            max_output_tokens=max_tokens + REASONING_TOKEN_RESERVE,
            reasoning={"effort": REASONING_EFFORT},
            instructions=system,
            input=user,
        )
        return response.output_text.strip()

    def parse(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> T:
        response = self.client.responses.parse(
            model=model or self.compile_model,
            max_output_tokens=max_tokens + REASONING_TOKEN_RESERVE,
            reasoning={"effort": REASONING_EFFORT},
            instructions=system,
            input=user,
            text_format=schema,
        )
        if response.output_parsed is None:
            reason = getattr(response, "incomplete_details", None) or getattr(
                response, "status", "unknown"
            )
            raise ProviderError(f"Structured parse returned no output (status={reason}).")
        return response.output_parsed

    def transcribe_pdf(self, path: Path) -> str:
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        response = self.client.responses.create(
            model=self.compile_model,
            max_output_tokens=16000 + REASONING_TOKEN_RESERVE,
            reasoning={"effort": REASONING_EFFORT},
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": path.name,
                            "file_data": f"data:application/pdf;base64,{data}",
                        },
                        {"type": "input_text", "text": TRANSCRIBE_INSTRUCTION},
                    ],
                }
            ],
        )
        return response.output_text.strip()

    def transcribe_image(self, path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        response = self.client.responses.create(
            model=self.compile_model,
            max_output_tokens=8000 + REASONING_TOKEN_RESERVE,
            reasoning={"effort": REASONING_EFFORT},
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:{media_type};base64,{data}",
                        },
                        {"type": "input_text", "text": TRANSCRIBE_INSTRUCTION},
                    ],
                }
            ],
        )
        return response.output_text.strip()

    def count_tokens(self, system: str, user: str, *, model: str | None = None) -> int:
        # OpenAI has no remote count endpoint; estimate locally with tiktoken,
        # falling back to a coarse character heuristic if it is unavailable.
        text = f"{system}\n{user}"
        try:
            import tiktoken

            try:
                enc = tiktoken.encoding_for_model(model or self.compile_model)
            except KeyError:
                enc = tiktoken.get_encoding("o200k_base")
            return len(enc.encode(text))
        except Exception:  # pragma: no cover - best-effort fallback
            return max(1, len(text) // 4)
