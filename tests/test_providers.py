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
