import stat

from llmwiki import keystore


def test_set_key_creates_file_with_0600(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = keystore.set_key("openai", "sk-abc123")
    assert path == tmp_path / "llmwiki" / ".env"
    assert "OPENAI_API_KEY=sk-abc123" in path.read_text("utf-8")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_set_key_replaces_without_duplicating(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    keystore.set_key("openai", "sk-old")
    keystore.set_key("anthropic", "sk-anth")
    keystore.set_key("openai", "sk-new")  # replace, not append

    stored = keystore.stored_keys()
    assert stored == {"OPENAI_API_KEY": "sk-new", "ANTHROPIC_API_KEY": "sk-anth"}
    # the openai key must appear exactly once
    body = (tmp_path / "llmwiki" / ".env").read_text("utf-8")
    assert body.count("OPENAI_API_KEY=") == 1


def test_load_into_env_respects_existing_and_parses_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    key_path = tmp_path / "llmwiki" / ".env"
    key_path.parent.mkdir(parents=True)
    # comment + export prefix + surrounding quotes should all be tolerated
    key_path.write_text(
        '# my keys\nexport OPENAI_API_KEY="sk-from-file"\nANTHROPIC_API_KEY=sk-anth\n',
        "utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-already-exported")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    keystore.load_into_env()

    import os

    # a real exported var wins; an unset one is filled from the file
    assert os.environ["OPENAI_API_KEY"] == "sk-already-exported"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-anth"


def test_resolve_env_maps_providers_and_passes_through(tmp_path, monkeypatch):
    assert keystore.resolve_env("openai") == "OPENAI_API_KEY"
    assert keystore.resolve_env("claude") == "ANTHROPIC_API_KEY"
    assert keystore.resolve_env("OPENAI_API_KEY") == "OPENAI_API_KEY"
