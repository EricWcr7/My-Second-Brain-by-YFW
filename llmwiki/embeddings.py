"""OpenAI-compatible embeddings, decoupled from the chat provider.

Semantic search needs an *embedding* model — a different model class from the
chat/reasoning model that writes pages and answers. Embeddings are deliberately
independent of the chat ``provider``: they go through an OpenAI-compatible
``/v1/embeddings`` endpoint, so semantic search works whether chat runs on OpenAI
or Anthropic, and can point at a local endpoint (Ollama, llama.cpp) via
``embed_base_url``.

This mirrors the provider layer's resilience/observability contract: SDK errors are
normalized to :class:`ProviderError`, and each call logs model + token counts +
duration — never text or keys. Keys come from the environment only (see the secrets
rule); the model is chosen *per call* so one ``Embedder`` serves every section's
configured strength.
"""

from __future__ import annotations

import logging
import math
import os
import time

from .config import Config
from .providers.base import ProviderError

logger = logging.getLogger("llmwiki.providers")


def validate_embedding_vectors(
    vectors: list[list[float]], expected_count: int, *, unit: str = "texts"
) -> list[list[float]]:
    """Reject malformed provider output before it can reach the vector store."""
    if len(vectors) != expected_count:
        raise ProviderError(
            f"Embeddings returned {len(vectors)} vectors for {expected_count} {unit}."
        )
    if not vectors:
        return vectors
    try:
        dimensions = {len(vector) for vector in vectors}
    except TypeError as e:
        raise ProviderError("Embeddings returned invalid vector values.") from e
    if len(dimensions) != 1:
        raise ProviderError("Embeddings returned vectors with inconsistent dimensions.")
    if dimensions == {0}:
        raise ProviderError("Embeddings returned empty vectors.")
    try:
        if any(not math.isfinite(float(value)) for vector in vectors for value in vector):
            raise ProviderError("Embeddings returned vectors with non-finite values.")
    except (TypeError, ValueError) as e:
        raise ProviderError("Embeddings returned non-numeric vector values.") from e
    return vectors


class Embedder:
    def __init__(self, config: Config):
        try:
            import openai
        except ImportError as e:  # pragma: no cover - import guard
            raise ProviderError(
                "The `openai` package is required for embeddings. "
                "Install with `pip install openai`."
            ) from e
        self.config = config
        # Some local OpenAI-compatible servers need no key; pass a placeholder so
        # the client constructs, and let real auth errors surface per call.
        api_key = os.environ.get(config.embed_api_key_env) or "no-key"
        try:
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=config.embed_base_url,  # None -> OpenAI default
                timeout=config.request_timeout,
                max_retries=config.max_retries,
            )
        except Exception as e:  # pragma: no cover
            raise ProviderError("Could not initialize the embeddings client.") from e
        self._openai = openai

    @property
    def available(self) -> bool:
        """Whether a call is worth attempting: a key is set, or a (local) endpoint."""
        return bool(
            os.environ.get(self.config.embed_api_key_env) or self.config.embed_base_url
        )

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        """Return one vector per input text, embedded with ``model`` (order preserved)."""
        if not texts:
            return []
        start = time.perf_counter()
        try:
            resp = self.client.embeddings.create(model=model, input=texts)
        except self._openai.OpenAIError as e:
            raise ProviderError(f"Embeddings failed ({type(e).__name__}): {e}") from e
        usage = getattr(resp, "usage", None)
        logger.info(
            "op=embed model=%s input_tokens=%s count=%d elapsed_s=%.2f",
            model,
            getattr(usage, "prompt_tokens", None),
            len(texts),
            time.perf_counter() - start,
        )
        items = sorted(resp.data, key=lambda d: d.index)
        if [item.index for item in items] != list(range(len(texts))):
            raise ProviderError("Embeddings returned invalid item indexes.")
        vectors = [list(item.embedding) for item in items]
        return validate_embedding_vectors(vectors, len(texts))


def make_embedder(config: Config) -> Embedder | None:
    """Build an :class:`Embedder`, or ``None`` when embeddings can't be used.

    Returns ``None`` if hybrid search is off or no usable endpoint/key is present,
    so callers degrade cleanly to BM25-only retrieval.
    """
    if not config.hybrid_search:
        return None
    try:
        embedder = Embedder(config)
    except ProviderError:
        return None
    return embedder if embedder.available else None
