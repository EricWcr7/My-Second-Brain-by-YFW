"""FastAPI app exposing the wiki pipelines as JSON for the web UI.

This is a thin wrapper: every endpoint reuses the existing functions in
``llmwiki`` (search/answer/lint/iter_pages/read_page) and changes no logic.
The ``provider_factory`` argument lets tests inject a fake provider.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from ..config import Config, load_config
from ..lint import lint
from ..providers import LLMProvider, get_provider
from ..query import answer
from ..search import search
from ..store import ensure_dir, read_page
from ..wiki import (
    PageRef,
    append_log,
    iter_pages,
    normalize_section,
    read_optional,
    rebuild_index,
    section_dirs,
    section_slug,
    section_to_relpath,
)

# Seeded top-level branches the UI relies on — never deletable via the web API.
_PROTECTED_SECTIONS = {"academic", "non-academic"}

STATIC_DIR = Path(__file__).parent / "static"

ProviderFactory = Callable[[Config], LLMProvider]


class _SPAStaticFiles(StaticFiles):
    """Serve the Vite build. Vite fingerprints JS/CSS/font filenames, so those
    may be cached freely; only ``index.html`` (unhashed) must always revalidate
    so a package upgrade picks up the new asset hashes immediately."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if getattr(response, "path", "").endswith("index.html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

# Environment variable holding the API key for each provider backend.
_PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


def _api_key_env(config: Config) -> str:
    """Name of the env var that holds the configured provider's API key."""
    return _PROVIDER_KEY_ENV.get(str(config.provider).lower(), "OPENAI_API_KEY")


def _has_api_key(config: Config) -> bool:
    return bool(os.environ.get(_api_key_env(config)))


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
    app = FastAPI(title="My Second Brain", docs_url=None, redoc_url=None)

    @app.get("/api/meta")
    def meta() -> dict:
        concepts = iter_pages(config, "concept")
        sources = iter_pages(config, "source")
        sections = sorted(
            {r.section for r in concepts}
            | {r.section for r in sources}
            | section_dirs(config)
        )
        return {
            "sections": sections,
            "concept_count": len(concepts),
            "source_count": len(sources),
            "default_section": config.default_section,
            "has_api_key": _has_api_key(config),
            "api_key_env": _api_key_env(config),
        }

    @app.get("/api/pages")
    def pages() -> list[dict]:
        refs = iter_pages(config, "concept") + iter_pages(config, "source")
        return [
            {"slug": r.slug, "title": r.title, "section": r.section, "type": r.page_type}
            for r in refs
        ]

    @app.post("/api/sections")
    def create_section(
        name: str = Body(..., embed=True),
        parent: str = Body("", embed=True),
    ) -> dict:
        """Scaffold a new child section (e.g. an Academic course) on disk.

        Creates the matching ``concepts/<section>`` and ``sources/<section>``
        directories, mirroring ``scaffold_vault``. Each segment goes through
        ``section_slug`` (case- and Unicode-preserving), so traversal is impossible
        while course codes (``example-course``) and non-Latin names keep their form. The
        UI sends ``parent`` = the current scope.
        """
        slug = section_slug(name)
        if not name.strip() or slug == "untitled":
            raise HTTPException(status_code=422, detail="Provide a name for the new section.")
        parent_norm = normalize_section(parent)
        section = normalize_section(f"{parent_norm}/{slug}" if parent_norm else slug)
        rel = section_to_relpath(section)
        targets = [config.concepts_dir / rel, config.source_pages_dir / rel]
        # Case-insensitive dup check so behavior matches on case-sensitive (Linux)
        # and case-insensitive (macOS) filesystems, and "example-course"/"example-course" can't
        # both exist.
        existing = {s.lower() for s in section_dirs(config)}
        if section.lower() in existing or any(t.exists() for t in targets):
            raise HTTPException(status_code=409, detail=f"Section '{section}' already exists.")
        for t in targets:
            ensure_dir(t)
        append_log(config, "section", section, detail="created via web UI")
        return {"section": section, "label": section.split("/")[-1]}

    @app.delete("/api/sections/{section:path}")
    def delete_section(section: str) -> dict:
        """Delete a course/branch: remove its ``concepts/<section>`` and
        ``sources/<section>`` directories (and everything inside them).

        The seeded ``academic``/``non-academic`` roots are protected. The section
        is resolved case-insensitively against the dirs on disk, so the URL casing
        need not match exactly.
        """
        norm = normalize_section(section)
        if not norm or norm.lower() in _PROTECTED_SECTIONS:
            raise HTTPException(status_code=403, detail="This branch cannot be deleted.")
        match = next(
            (s for s in section_dirs(config) if s.lower() == norm.lower()), None
        )
        if match is None:
            raise HTTPException(status_code=404, detail=f"Section '{section}' not found.")
        rel = section_to_relpath(match)
        for t in (config.concepts_dir / rel, config.source_pages_dir / rel):
            if t.exists():
                shutil.rmtree(t)
        rebuild_index(config)  # drop the deleted pages from index.md / home overview
        append_log(config, "section", match, detail="deleted via web UI")
        return {"section": match}

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
            "section": ref.section,
            "type": ref.page_type,
            "content": doc.content,
        }

    @app.get("/api/search")
    def search_endpoint(
        q: str = Query(...),
        section: str | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        hits = search(config, q, top_k=top_k or config.search_top_k, section=section)
        return [
            {
                "slug": h.ref.slug,
                "title": h.ref.title,
                "section": h.ref.section,
                "score": round(h.score, 3),
            }
            for h in hits
        ]

    @app.post("/api/query")
    def query_endpoint(
        question: str = Body(..., embed=True),
        section: str | None = Body(None, embed=True),
    ) -> dict:
        if not _has_api_key(config):
            env = _api_key_env(config)
            raise HTTPException(
                status_code=503,
                detail=f"{env} is not set; set it and restart to ask questions.",
            )
        result = answer(config, provider_factory(config), question, section=section)
        return {"answer": result.answer, "pages_used": result.pages_used}

    @app.get("/api/lint")
    def lint_endpoint(section: str | None = None, deep: bool = False) -> list[dict]:
        provider = None
        if deep:
            if not _has_api_key(config):
                raise HTTPException(
                    status_code=503,
                    detail=f"{_api_key_env(config)} is not set; deep lint needs it.",
                )
            provider = provider_factory(config)
        issues = lint(config, provider=provider, deep=deep, section=section)
        return [{"level": i.level, "page": i.page, "message": i.message} for i in issues]

    # check_dir=False so create_app works before the frontend is built (tests,
    # fresh checkouts); requests simply 404 until `vite build` populates static/.
    app.mount("/", _SPAStaticFiles(directory=STATIC_DIR, html=True, check_dir=False), name="static")
    return app
