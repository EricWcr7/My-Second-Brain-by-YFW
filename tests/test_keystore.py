import stat

from llmwiki import keystore


def test_set_key_creates_file_with_0600(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = keystore.set_key("openai", "test-openai-key")
    assert path == tmp_path / "llmwiki" / ".env"
    assert "OPENAI_API_KEY=test-openai-key" in path.read_text("utf-8")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_set_key_replaces_without_duplicating(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    keystore.set_key("openai", "test-openai-old")
    keystore.set_key("anthropic", "test-anthropic-key")
    keystore.set_key("openai", "test-openai-new")  # replace, not append

    stored = keystore.stored_keys()
    assert stored == {
        "OPENAI_API_KEY": "test-openai-new",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }
    # the openai key must appear exactly once
    body = (tmp_path / "llmwiki" / ".env").read_text("utf-8")
    assert body.count("OPENAI_API_KEY=") == 1


def test_load_into_env_overrides_existing_and_parses_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    key_path = tmp_path / "llmwiki" / ".env"
    key_path.parent.mkdir(parents=True)
    # comment + export prefix + surrounding quotes should all be tolerated
    key_path.write_text(
        '# test values\nexport OPENAI_API_KEY="test-from-file"\nANTHROPIC_API_KEY=test-anthropic-key\n',
        "utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-already-exported")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    keystore.load_into_env()

    import os

    # the stored key is authoritative: a stale exported var is overridden,
    # and an unset one is filled from the file
    assert os.environ["OPENAI_API_KEY"] == "test-from-file"
    assert os.environ["ANTHROPIC_API_KEY"] == "test-anthropic-key"


def test_resolve_env_maps_providers_and_passes_through(tmp_path, monkeypatch):
    assert keystore.resolve_env("openai") == "OPENAI_API_KEY"
    assert keystore.resolve_env("claude") == "ANTHROPIC_API_KEY"
    assert keystore.resolve_env("OPENAI_API_KEY") == "OPENAI_API_KEY"
