"""PDF loader: PyMuPDF text extraction, with a vision fallback for scanned/math PDFs."""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..providers.base import LLMProvider
from .base import LoaderError, LoadResult


def _extract_text(path: Path) -> tuple[str, int]:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:  # pragma: no cover
        raise LoaderError("PyMuPDF is required for PDF files (`pip install pymupdf`).") from e
    parts: list[str] = []
    with fitz.open(path) as doc:
        page_count = doc.page_count
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                parts.append(f"<!-- page {i} -->\n{text}")
    return "\n\n".join(parts), page_count


def load(
    path: Path,
    *,
    config: Config,
    provider: LLMProvider,
    force_vision: bool = False,
) -> LoadResult:
    text, page_count = _extract_text(path)
    threshold = config.pdf_vision_min_chars_per_page * max(page_count, 1)
    use_vision = force_vision or len(text) < threshold
    if use_vision:
        markdown = provider.transcribe_pdf(path)
        if not markdown.strip():
            raise LoaderError(f"Vision transcription produced no text for {path}.")
    else:
        markdown = text
    return LoadResult(markdown=markdown, kind="pdf", title=path.stem)
