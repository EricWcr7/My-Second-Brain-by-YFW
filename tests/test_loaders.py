import pytest

from llmwiki.loaders import LoaderError, is_url, load_source
from llmwiki.loaders import markdown_loader, pdf_loader

from tests.fakes import FakeProvider


def _make_pdf(path, n_pages: int) -> None:
    """Write a real ``n_pages``-page PDF (content irrelevant; vision is forced)."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    for i in range(n_pages):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}")
    doc.save(str(path))
    doc.close()


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


def test_large_scanned_pdf_transcribed_in_page_batches(tmp_path, vault):
    pdf = tmp_path / "scan.pdf"
    _make_pdf(pdf, n_pages=5)
    vault.pdf_vision_batch_pages = 2  # 5 pages -> batches [1-2], [3-4], [5]
    provider = FakeProvider()
    result = pdf_loader.load(pdf, config=vault, provider=provider, force_vision=True)
    assert provider.calls.count("transcribe_pdf") == 3
    for marker in ("<!-- page 1 -->", "<!-- page 3 -->", "<!-- page 5 -->"):
        assert marker in result.markdown


def test_small_scanned_pdf_is_single_call(tmp_path, vault):
    pdf = tmp_path / "scan.pdf"
    _make_pdf(pdf, n_pages=3)
    vault.pdf_vision_batch_pages = 10  # 3 pages fit one batch -> one call
    provider = FakeProvider()
    result = pdf_loader.load(pdf, config=vault, provider=provider, force_vision=True)
    assert provider.calls.count("transcribe_pdf") == 1
    assert "Transcribed PDF" in result.markdown


def test_concurrent_batches_reassembled_in_page_order(tmp_path, vault):
    class _PerBatchProvider(FakeProvider):
        # Return content keyed to the batch sub-PDF so order can be asserted even
        # when batches complete out of order under concurrency.
        def transcribe_pdf(self, path):
            self.calls.append("transcribe_pdf")
            return f"BODY-{path.stem}"  # batch-0, batch-2, batch-4

    pdf = tmp_path / "scan.pdf"
    _make_pdf(pdf, n_pages=5)
    vault.pdf_vision_batch_pages = 2  # -> batches starting at pages 1, 3, 5
    vault.pdf_vision_max_concurrency = 3  # all three at once
    md = pdf_loader.load(pdf, config=vault, provider=_PerBatchProvider(), force_vision=True).markdown
    assert md.index("BODY-batch-0") < md.index("BODY-batch-2") < md.index("BODY-batch-4")
    assert md.index("<!-- page 1 -->") < md.index("<!-- page 3 -->") < md.index("<!-- page 5 -->")
