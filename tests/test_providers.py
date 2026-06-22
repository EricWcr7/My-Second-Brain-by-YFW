"""Provider selection and config wiring (no API calls)."""

from __future__ import annotations

from pathlib import Path

import pytest

import llmwiki.providers.anthropic_provider as ap
import llmwiki.providers.openai_provider as op
from llmwiki.config import Config, load_config
from llmwiki.providers import ProviderError, get_provider


def test_config_defaults_to_openai_with_provider_default_models():
    cfg = Config(root=Path("/tmp"))
    assert cfg.provider == "openai"
    assert cfg.compile_model is None
    assert cfg.cheap_model is None


def test_load_config_reads_provider_and_overrides(vault):
    vault.config_file.write_text(
        '[settings]\nprovider = "anthropic"\ncompile_model = "claude-opus-4-8"\n',
        "utf-8",
    )
    cfg = load_config(vault.root)
    assert cfg.provider == "anthropic"
    assert cfg.compile_model == "claude-opus-4-8"
    assert cfg.cheap_model is None


def test_get_provider_defaults_to_openai(vault, monkeypatch):
    captured = {}
    monkeypatch.setattr(op, "OpenAIProvider", lambda config: captured.setdefault("c", config))
    assert get_provider(vault) is vault


def test_get_provider_selects_anthropic_aliases(vault, monkeypatch):
    monkeypatch.setattr(ap, "AnthropicProvider", lambda config: "ANTHROPIC")
    for name in ("anthropic", "claude"):
        vault.provider = name
        assert get_provider(vault) == "ANTHROPIC"


def test_get_provider_unknown_raises(vault):
    vault.provider = "bananas"
    with pytest.raises(ProviderError, match="Unknown provider"):
        get_provider(vault)


def test_openai_defaults_to_gpt55(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))
    assert provider.compile_model == "gpt-5.5"
    assert provider.cheap_model == "gpt-5.5"


def test_openai_requests_use_high_reasoning(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))

    captured: dict = {}

    class _Resp:
        output_text = "ok"

    class _Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Resp()

    provider.client = type("_Client", (), {"responses": _Responses()})()
    provider.complete("system", "user")

    assert captured["model"] == "gpt-5.5"
    assert captured["reasoning"] == {"effort": "high"}
    assert op.REASONING_EFFORT == "high"


def test_openai_client_uses_config_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp"), request_timeout=12.0, max_retries=5))
    # Resilience knobs flow from config into the SDK client.
    assert provider.client.timeout == 12.0
    assert provider.client.max_retries == 5


def test_openai_with_timeout_scopes_a_longer_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp"), request_timeout=12.0, max_retries=5))
    scoped = provider.with_timeout(3600.0)
    # A distinct provider + client carrying the override; the original is untouched
    # and other resilience knobs are preserved.
    assert scoped is not provider and scoped.client is not provider.client
    assert scoped.client.timeout == 3600.0
    assert scoped.client.max_retries == 5
    assert provider.client.timeout == 12.0


def test_openai_records_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))

    class _Usage:
        input_tokens = 11
        output_tokens = 7

    class _Resp:
        output_text = "ok"
        usage = _Usage()

    class _Responses:
        def create(self, **kwargs):
            return _Resp()

    provider.client = type("_Client", (), {"responses": _Responses()})()
    assert provider.complete("system", "user") == "ok"
    assert provider.last_usage.input_tokens == 11
    assert provider.last_usage.output_tokens == 7


def test_openai_normalizes_sdk_errors(monkeypatch):
    import openai

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))

    class _Responses:
        def create(self, **kwargs):
            raise openai.OpenAIError("rate limited")

    provider.client = type("_Client", (), {"responses": _Responses()})()
    with pytest.raises(ProviderError, match="OpenAI complete failed"):
        provider.complete("system", "user")


def test_anthropic_client_uses_config_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp"), request_timeout=12.0, max_retries=5))
    assert provider.client.timeout == 12.0
    assert provider.client.max_retries == 5


def test_anthropic_with_timeout_scopes_a_longer_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp"), request_timeout=12.0, max_retries=5))
    scoped = provider.with_timeout(3600.0)
    assert scoped is not provider and scoped.client is not provider.client
    assert scoped.client.timeout == 3600.0
    assert scoped.client.max_retries == 5
    assert provider.client.timeout == 12.0


def test_anthropic_normalizes_count_tokens_errors(monkeypatch):
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp")))

    class _Messages:
        def count_tokens(self, **kwargs):
            raise anthropic.AnthropicError("boom")

    provider.client = type("_Client", (), {"messages": _Messages()})()
    with pytest.raises(ProviderError, match="Anthropic count_tokens failed"):
        provider.count_tokens("system", "user")
