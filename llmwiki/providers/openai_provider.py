"""OpenAI implementation of :class:`LLMProvider`.

Uses the official ``openai`` SDK and its Responses API. The API key is read from
the environment (``OPENAI_API_KEY``). This is the default backend; switch to
Claude by setting ``provider = "anthropic"`` in ``.llmwiki/config.toml``.

Every operation runs on a GPT-5.5+ reasoning model at ``high`` reasoning effort
(default: ``gpt-5.6-sol``).
"""

from __future__ import annotations

import base64
import copy
import logging
import mimetypes
import time
from pathlib import Path

from ..config import Config
from .base import LLMProvider, ProviderError, T, Usage

logger = logging.getLogger("llmwiki.providers")

# Reasoning effort applied to every call. high is supported on gpt-5.5+.
REASONING_EFFORT = "high"
# Reasoning tokens count toward ``max_output_tokens``; reserve headroom on top of
# the caller's output budget so high reasoning can't starve the visible answer.
REASONING_TOKEN_RESERVE = 25_000

TRANSCRIBE_INSTRUCTION = (
    "Transcribe this document into clean, faithful Markdown for an academic study "
    "wiki. Preserve ALL mathematics as LaTeX (inline `$...$`, display `$$...$$`) "
    "using the notation in the source. Keep definitions, theorems, assumptions, "
    "proofs, and examples intact and in order. Describe figures/diagrams briefly "
    "in text. Do not summarize or omit content. Output only the Markdown."
)


class OpenAIProvider(LLMProvider):
    DEFAULT_COMPILE_MODEL = "gpt-5.6-sol"
    DEFAULT_CHEAP_MODEL = "gpt-5.6-sol"

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
            # timeout/max_retries make transient network failures resilient and
            # bounded instead of hanging or crashing the pipeline.
            self.client = openai.OpenAI(
                timeout=config.request_timeout, max_retries=config.max_retries
            )
        except Exception as e:  # missing key etc.
            raise ProviderError(
                "Could not initialize the OpenAI client. Set OPENAI_API_KEY."
            ) from e

    def with_timeout(self, timeout: float) -> "OpenAIProvider":
        # Scope a longer per-request timeout (ingest) without mutating the shared
        # provider: ``with_options`` returns a copied client with the override.
        clone = copy.copy(self)
        clone.client = self.client.with_options(timeout=timeout)
        return clone

    def _invoke(self, op: str, model: str, call):
        """Run an SDK call: time it, normalize errors, record usage safely.

        SDK exceptions become :class:`ProviderError` so the web layer renders a
        clean 503 and the CLI a clean message instead of a raw traceback. Usage is
        logged for observability — model + token counts + duration only, **never**
        prompt text or keys.
        """
        start = time.perf_counter()
        try:
            response = call()
        except self._openai.OpenAIError as e:
            raise ProviderError(f"OpenAI {op} failed ({type(e).__name__}): {e}") from e
        usage = getattr(response, "usage", None)
        self.last_usage = Usage(
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
        logger.info(
            "op=%s provider=openai model=%s input_tokens=%s output_tokens=%s elapsed_s=%.2f",
            op,
            model,
            self.last_usage.input_tokens,
            self.last_usage.output_tokens,
            time.perf_counter() - start,
        )
        return response

    def complete(
        self, system: str, user: str, *, model: str | None = None, max_tokens: int = 16000
    ) -> str:
        model = model or self.compile_model
        response = self._invoke(
            "complete",
            model,
            lambda: self.client.responses.create(
                model=model,
                max_output_tokens=max_tokens + REASONING_TOKEN_RESERVE,
                reasoning={"effort": REASONING_EFFORT},
                instructions=system,
                input=user,
            ),
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
        model = model or self.compile_model
        response = self._invoke(
            "parse",
            model,
            lambda: self.client.responses.parse(
                model=model,
                max_output_tokens=max_tokens + REASONING_TOKEN_RESERVE,
                reasoning={"effort": REASONING_EFFORT},
                instructions=system,
                input=user,
                text_format=schema,
            ),
        )
        if response.output_parsed is None:
            reason = getattr(response, "incomplete_details", None) or getattr(
                response, "status", "unknown"
            )
            raise ProviderError(f"Structured parse returned no output (status={reason}).")
        return response.output_parsed

    def transcribe_pdf(self, path: Path) -> str:
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        response = self._invoke(
            "transcribe_pdf",
            self.compile_model,
            lambda: self.client.responses.create(
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
            ),
        )
        return response.output_text.strip()

    def transcribe_image(self, path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        response = self._invoke(
            "transcribe_image",
            self.compile_model,
            lambda: self.client.responses.create(
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
            ),
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
