import pytest

from llmwiki.loaders import LoaderError, is_url, load_source
from llmwiki.loaders import markdown_loader

from tests.fakes import FakeProvider


def test_is_url():
    assert is_url("https://example.com")
    assert is_url("http://example.com")
    assert not is_url("/tmp/notes.md")


def test_markdown_loader_uses_h1_title(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# Chain Rule\n\nThe derivative...", "utf-8")
    result = markdown_loader.load(f)
    assert result.kind == "markdown"
    assert result.title == "Chain Rule"
    assert "derivative" in result.markdown


def test_load_source_unsupported_extension(tmp_path, vault):
    f = tmp_path / "data.xyz"
    f.write_text("x", "utf-8")
    with pytest.raises(LoaderError):
        load_source(str(f), config=vault, provider=FakeProvider())


def test_load_source_missing_file(vault):
    with pytest.raises(LoaderError):
        load_source("/no/such/file.md", config=vault, provider=FakeProvider())


def test_load_source_image_uses_vision(tmp_path, vault):
    img = tmp_path / "diagram.png"
    img.write_bytes(b"\x89PNG\r\n")  # content irrelevant; provider is faked
    result = load_source(str(img), config=vault, provider=FakeProvider())
    assert result.kind == "image"
    assert "Transcribed image" in result.markdown
