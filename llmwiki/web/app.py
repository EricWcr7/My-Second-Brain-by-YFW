"""FastAPI app exposing the wiki pipelines as JSON for the web UI.

This is a thin wrapper: every endpoint reuses the existing functions in
``llmwiki`` (search/answer/lint/iter_pages/read_page) and changes no logic.
The ``provider_factory`` argument lets tests inject a fake provider.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from ..config import Config, load_config
from ..lint import lint
from ..providers import LLMProvider, get_provider
from ..query import answer
from ..search import search
from ..store import read_page
from ..wiki import PageRef, iter_pages, read_optional

STATIC_DIR = Path(__file__).parent / "static"

ProviderFactory = Callable[[Config], LLMProvider]


def _has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _page_index(config: Config) -> dict[str, PageRef]:
    """Map slug -> PageRef across concepts then sources (first match wins)."""
    index: dict[str, PageRef] = {}
    for ref in iter_pages(config, "concept") + iter_pages(config, "source"):
        index.setdefault(ref.slug, ref)
    return index


def create_app(
    config: Config | None = None,
    provider_factory: ProviderFactory = get_provider,
) -> FastAPI:
    config = config or load_config()
    app = FastAPI(title="llmwiki", docs_url=None, redoc_url=None)

    @app.get("/api/meta")
    def meta() -> dict:
        concepts = iter_pages(config, "concept")
        sources = iter_pages(config, "source")
        courses = sorted({r.course for r in concepts} | {r.course for r in sources})
        return {
            "courses": courses,
            "concept_count": len(concepts),
            "source_count": len(sources),
            "default_course": config.default_course,
            "has_api_key": _has_api_key(),
        }

    @app.get("/api/pages")
    def pages() -> list[dict]:
        refs = iter_pages(config, "concept") + iter_pages(config, "source")
        return [
            {"slug": r.slug, "title": r.title, "course": r.course, "type": r.page_type}
            for r in refs
        ]

    @app.get("/api/home")
    def home() -> dict:
        content = read_optional(config.overview_file) or read_optional(config.index_file)
        return {"title": "Overview", "content": content}

    @app.get("/api/page/{slug}")
    def page(slug: str) -> dict:
        ref = _page_index(config).get(slug)
        if ref is None:
            raise HTTPException(status_code=404, detail=f"no page with slug {slug!r}")
        doc = read_page(ref.path)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"page file missing for {slug!r}")
        return {
            "slug": ref.slug,
            "title": ref.title,
            "course": ref.course,
            "type": ref.page_type,
            "content": doc.content,
        }

    @app.get("/api/search")
    def search_endpoint(
        q: str = Query(...),
        course: str | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        hits = search(config, q, top_k=top_k or config.search_top_k, course=course)
        return [
            {
                "slug": h.ref.slug,
                "title": h.ref.title,
                "course": h.ref.course,
                "score": round(h.score, 3),
            }
            for h in hits
        ]

    @app.post("/api/query")
    def query_endpoint(
        question: str = Body(..., embed=True),
        course: str | None = Body(None, embed=True),
    ) -> dict:
        if not _has_api_key():
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY is not set; set it and restart to ask questions.",
            )
        result = answer(config, provider_factory(config), question, course=course)
        return {"answer": result.answer, "pages_used": result.pages_used}

    @app.get("/api/lint")
    def lint_endpoint(course: str | None = None, deep: bool = False) -> list[dict]:
        provider = None
        if deep:
            if not _has_api_key():
                raise HTTPException(
                    status_code=503,
                    detail="ANTHROPIC_API_KEY is not set; deep lint needs it.",
                )
            provider = provider_factory(config)
        issues = lint(config, provider=provider, deep=deep, course=course)
        return [{"level": i.level, "page": i.page, "message": i.message} for i in issues]

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
