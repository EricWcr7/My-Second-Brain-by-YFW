"""LLM provider layer."""

from __future__ import annotations

from ..config import Config
from .base import LLMProvider, ProviderError


def get_provider(config: Config) -> LLMProvider:
    """Return the configured provider (default: OpenAI)."""
    provider = str(config.provider).lower()
    if provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(config)
    if provider in ("anthropic", "claude"):
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(config)
    raise ProviderError(
        f"Unknown provider: {provider!r}. Set provider to 'openai' or 'anthropic'."
    )


__all__ = ["LLMProvider", "ProviderError", "get_provider"]
