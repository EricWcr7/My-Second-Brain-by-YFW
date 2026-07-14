"""Provider selection and config wiring (no API calls)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import llmwiki.providers.anthropic_provider as ap
import llmwiki.providers.openai_provider as op
from llmwiki.config import Config, load_config
from llmwiki.providers import ProviderError, get_provider
from llmwiki.providers.base import ChatMessage


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


def test_openai_defaults_to_gpt56_sol(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))
    assert provider.compile_model == "gpt-5.6-sol"
    assert provider.cheap_model == "gpt-5.6-sol"


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

    assert captured["model"] == "gpt-5.6-sol"
    assert captured["reasoning"] == {"effort": "high"}
    assert op.REASONING_EFFORT == "high"


def test_openai_chat_requests_max_reasoning_and_collects_summaries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))
    captured: dict = {}

    class _Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text=" Final answer. ",
                output=[
                    {
                        "type": "reasoning",
                        "summary": [
                            {"type": "summary_text", "text": "First summary."},
                            {"type": "summary_text", "text": "Second summary."},
                        ],
                    },
                    {"type": "message", "content": []},
                    {
                        "type": "reasoning",
                        "summary": [{"type": "summary_text", "text": "Third summary."}],
                    },
                ],
            )

    provider.client = type("_Client", (), {"responses": _Responses()})()
    result = provider.chat("system", [ChatMessage(role="user", text="question")], effort="max")

    assert captured["model"] == "gpt-5.6-sol"
    assert captured["reasoning"] == {"effort": "max", "summary": "auto"}
    assert captured["max_output_tokens"] == 16_000 + op.REASONING_TOKEN_RESERVE
    assert result.text == "Final answer."
    assert result.reasoning_summary == "First summary.\n\nSecond summary.\n\nThird summary."


def test_openai_chat_missing_summary_is_none(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pytest.importorskip("openai")
    provider = op.OpenAIProvider(Config(root=Path("/tmp")))

    class _Responses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text="answer", output=[])

    provider.client = type("_Client", (), {"responses": _Responses()})()
    result = provider.chat("system", [ChatMessage(role="user", text="question")], effort="max")
    assert result.reasoning_summary is None


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


class _AnthropicStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_final_message(self):
        return self.message


def test_anthropic_chat_requests_adaptive_max_and_separates_summary(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp")))
    captured: dict = {}
    message = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="First summary."),
            SimpleNamespace(type="text", text="Final "),
            SimpleNamespace(type="thinking", thinking="Second summary."),
            SimpleNamespace(type="text", text="answer."),
        ],
        stop_reason="end_turn",
    )

    class _Messages:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return _AnthropicStream(message)

    provider.client = type("_Client", (), {"messages": _Messages()})()
    result = provider.chat(
        "system",
        [ChatMessage(role="user", text="question")],
        model="claude-fable-5",
        max_tokens=64_000,
        effort="max",
    )

    assert captured["model"] == "claude-fable-5"
    assert captured["max_tokens"] == 64_000
    assert captured["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert captured["output_config"] == {"effort": "max"}
    assert result.text == "Final answer."
    assert result.reasoning_summary == "First summary.\n\nSecond summary."


def test_anthropic_chat_missing_summary_is_none(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp")))
    message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="answer")],
        stop_reason="end_turn",
    )

    class _Messages:
        def stream(self, **kwargs):
            return _AnthropicStream(message)

    provider.client = type("_Client", (), {"messages": _Messages()})()
    result = provider.chat(
        "system",
        [ChatMessage(role="user", text="question")],
        model="claude-fable-5",
        effort="max",
    )
    assert result.reasoning_summary is None


def test_anthropic_non_fable_raw_thinking_is_not_exposed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp")))
    message = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="raw hidden reasoning"),
            SimpleNamespace(type="text", text="answer"),
        ],
        stop_reason="end_turn",
    )
    captured: dict = {}

    class _Messages:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return _AnthropicStream(message)

    provider.client = type("_Client", (), {"messages": _Messages()})()
    result = provider.chat("system", [ChatMessage(role="user", text="question")], effort="xhigh")

    assert captured["thinking"] == {"type": "adaptive"}
    assert "output_config" not in captured
    assert result.reasoning_summary is None


def test_anthropic_refusal_becomes_clean_provider_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    pytest.importorskip("anthropic")
    provider = ap.AnthropicProvider(Config(root=Path("/tmp")))
    message = SimpleNamespace(
        content=[],
        stop_reason="refusal",
        # anthropic 0.79 preserves this newly added response field as a dict.
        stop_details={"category": "medical_advice"},
    )

    class _Messages:
        def stream(self, **kwargs):
            return _AnthropicStream(message)

    provider.client = type("_Client", (), {"messages": _Messages()})()
    with pytest.raises(ProviderError, match="refused.*medical_advice"):
        provider.chat("system", [ChatMessage(role="user", text="question")], effort="max")
