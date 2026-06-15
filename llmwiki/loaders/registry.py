"""Dispatch a source spec (file path or URL) to the right loader."""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..providers.base import LLMProvider
from . import docx_loader, image_loader, markdown_loader, pdf_loader, pptx_loader, web_loader
from .base import LoaderError, LoadResult

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
TEXT_EXTS = {".md", ".markdown", ".txt"}


def is_url(spec: str) -> bool:
    return spec.startswith(("http://", "https://"))


def load_source(
    spec: str,
    *,
    config: Config,
    provider: LLMProvider,
    force_vision: bool = False,
) -> LoadResult:
    if is_url(spec):
        return web_loader.load(spec)

    path = Path(spec)
    if not path.exists():
        raise LoaderError(f"No such file: {path}")
    suffix = path.suffix.lower()

    if suffix in TEXT_EXTS:
        return markdown_loader.load(path)
    if suffix == ".pdf":
        return pdf_loader.load(
            path, config=config, provider=provider, force_vision=force_vision
        )
    if suffix == ".docx":
        return docx_loader.load(path)
    if suffix == ".pptx":
        return pptx_loader.load(path)
    if suffix in IMAGE_EXTS:
        return image_loader.load(path, provider=provider)
    raise LoaderError(
        f"Unsupported source type: {suffix or path.name}. "
        f"Supported: {sorted(TEXT_EXTS | {'.pdf', '.docx', '.pptx'} | IMAGE_EXTS)} and URLs."
    )
