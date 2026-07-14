"""Web URL loader: fetch a page and extract the main content as Markdown."""

from __future__ import annotations

from .base import LoaderError, LoadResult

_UA = (
    "Mozilla/5.0 (compatible; my-second-brain-by-yfw/1.0.0; "
    "+https://github.com/EricWcr7/My-Second-Brain-by-YFW)"
)


def load(url: str, **_kwargs) -> LoadResult:
    try:
        import httpx
    except ImportError as e:  # pragma: no cover
        raise LoaderError("httpx is required for web URLs.") from e
    try:
        import trafilatura
    except ImportError as e:  # pragma: no cover
        raise LoaderError("trafilatura is required for web URLs.") from e

    try:
        resp = httpx.get(
            url, follow_redirects=True, timeout=30.0, headers={"User-Agent": _UA}
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise LoaderError(f"Could not fetch {url}: {e}") from e

    html = resp.text
    markdown = trafilatura.extract(
        html, output_format="markdown", include_links=False, include_comments=False
    )
    if not markdown:
        markdown = trafilatura.extract(html) or ""
    if not markdown.strip():
        raise LoaderError(f"Could not extract readable content from {url}.")

    title = url
    meta = trafilatura.extract_metadata(html)
    if meta and meta.title:
        title = meta.title

    return LoadResult(markdown=markdown, kind="web", title=title)
