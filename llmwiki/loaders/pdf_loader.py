"""PDF loader: PyMuPDF text extraction, with a vision fallback for scanned/math PDFs."""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _transcribe_by_pages(
    path: Path, provider: LLMProvider, batch_pages: int, max_concurrency: int
) -> str:
    """Vision-transcribe a scanned/image PDF in page-range batches.

    A single vision call over a very large PDF blows the model's context window
    and is capped at the provider's output-token limit (silently truncating the
    transcription). Splitting the PDF into ``batch_pages``-page sub-PDFs keeps each
    call bounded; a ``<!-- page N -->`` marker per batch (matching the text path)
    gives the downstream segmented-ingest split deterministic boundaries. A PDF
    that fits in one batch is a single call — the original behavior.

    The batches are independent and the time is network wait, so up to
    ``max_concurrency`` of them are transcribed at once (bounded to stay under the
    provider's rate limits). Results are reassembled in page order regardless of
    completion order. (Concurrent calls race on the provider's ``last_usage``
    snapshot — that's observability only; per-call usage is still logged.)

    Every batch is attempted even when a sibling fails; if any batch can't be
    transcribed the whole transcription is aborted with the failed page ranges
    named, rather than silently dropping pages — the source's provenance must stay
    complete, so a partial scan is never written.
    """
    import fitz  # PyMuPDF; presence already ensured by _extract_text

    batch_pages = max(batch_pages, 1)
    with fitz.open(path) as src, tempfile.TemporaryDirectory() as tmpdir:
        # Slice into per-batch sub-PDFs up front (fitz work is serial and cheap);
        # the slow per-batch vision calls are overlapped below. ``end`` is the
        # 0-based inclusive last page, retained so a failure can name its pages.
        batches: list[tuple[int, int, Path]] = []
        for start in range(0, src.page_count, batch_pages):
            end = min(start + batch_pages, src.page_count) - 1
            batch_path = Path(tmpdir) / f"batch-{start}.pdf"
            with fitz.open() as out:
                out.insert_pdf(src, from_page=start, to_page=end)
                out.save(batch_path)
            batches.append((start, end, batch_path))

        def _transcribe(batch: tuple[int, int, Path]) -> tuple[int, str]:
            start, _end, batch_path = batch
            return start, provider.transcribe_pdf(batch_path).strip()

        # Collect successes and failures separately so one bad batch neither
        # abandons its in-flight siblings nor masks the others' failures.
        results: list[tuple[int, str]] = []
        failures: list[tuple[int, int]] = []  # (start, end) of batches that errored
        workers = max(1, min(max_concurrency, len(batches)))
        if workers == 1:
            for batch in batches:
                try:
                    results.append(_transcribe(batch))
                except Exception:
                    failures.append((batch[0], batch[1]))
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_transcribe, b): b for b in batches}
                for future in as_completed(futures):
                    batch = futures[future]
                    try:
                        results.append(future.result())
                    except Exception:
                        failures.append((batch[0], batch[1]))

    if failures:
        ranges = ", ".join(
            f"{s + 1}–{e + 1}" if e > s else f"{s + 1}" for s, e in sorted(failures)
        )
        raise LoaderError(
            f"Vision transcription failed for page(s) {ranges} of {path.name}; "
            "no pages were written — retry the ingest."
        )

    parts = [
        f"<!-- page {start + 1} -->\n{text}" for start, text in sorted(results) if text
    ]  # skip blank batches; a wholly empty PDF raises below
    if not parts:
        raise LoaderError(f"Vision transcription produced no text for {path}.")
    return "\n\n".join(parts)


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
        markdown = _transcribe_by_pages(
            path,
            provider,
            config.pdf_vision_batch_pages,
            config.pdf_vision_max_concurrency,
        )
    else:
        markdown = text
    return LoadResult(markdown=markdown, kind="pdf", title=path.stem)
