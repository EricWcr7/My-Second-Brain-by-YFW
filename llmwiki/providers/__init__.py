"""LLM provider layer."""

from __future__ import annotations

from ..config import Config
from .base import LLMProvider, ProviderError


def get_provider(config: Config) -> LLMProvider:
    """Return the configured provider. Claude is the only backend for now."""
    provider = str(config.extra.get("provider", "anthropic")).lower()
    if provider in ("anthropic", "claude"):
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(config)
    raise ProviderError(f"Unknown provider: {provider!r}")


__all__ = ["LLMProvider", "ProviderError", "get_provider"]
