"""FastAPI app exposing the wiki pipelines as JSON for the web UI.

This is a thin wrapper: every endpoint reuses the existing functions in
``llmwiki`` (search/answer/lint/iter_pages/read_page) and changes no logic.
The ``provider_factory`` argument lets tests inject a fake provider.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import Response
from starlette.types import Scope

from .. import overrides
from ..config import Config, load_config
from ..embeddings import make_embedder
from ..indexing import reindex_all
from ..ingest import ingest
from ..lint import lint
from ..loaders import LoaderError, load_source
from ..loaders.registry import IMAGE_EXTS, TEXT_EXTS
from ..providers import LLMProvider, ProviderError, get_provider
from ..query import answer
from ..search import search
from ..store import ensure_dir, read_page
from ..vectorindex import VectorIndexUnavailable
from ..overview import refresh_overview
from ..wiki import (
    PageRef,
    append_log,
    concept_path,
    iter_pages,
    normalize_section,
    overview_path,
    purge_page,
    purge_section,
    read_optional,
    section_dirs,
    section_slug,
    section_to_relpath,
    source_path,
)

# Seeded top-level branch the UI relies on — never deletable via the web API.
_PROTECTED_SECTIONS = {"academic"}

# Every extension the loaders can ingest — the single source of truth the web UI
# uses for its upload `accept` filter (mirrors loaders.registry's dispatch).
SUPPORTED_EXTS = sorted(TEXT_EXTS | {".pdf", ".docx", ".pptx"} | IMAGE_EXTS)

STATIC_DIR = Path(__file__).parent / "static"

ProviderFactory = Callable[[Config], LLMProvider]


def _section_label(section: str) -> str:
    return section.split("/")[-1] if section else "General"


class OverrideUpdate(BaseModel):
    """Apply per-section overrides of the LLM instruction set.

    ``set`` writes each ``component -> text`` override; ``reset`` removes the named
    components (re-inheriting the general default). Both are applied to every
    section in ``sections`` (``""`` = the General baseline), so one edit can fan
    out to several branches at once.
    """

    sections: list[str]
    set: dict[str, str] = {}
    reset: list[str] = []


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
            "supported_exts": SUPPORTED_EXTS,
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
        """Delete a course/branch and wipe *everything* filed under it.

        Removes the ``concepts/<section>`` and ``sources/<section>`` page subtrees
        plus the artifacts the old behavior stranded — the ``state.json`` ledger
        records for sources here (and their normalized cache / ``raw/`` bytes), the
        per-section overrides, and the deleted concepts' vector-index chunks — so
        orphaned records and bytes don't accumulate and search can't surface dead
        pages. (Re-ingest never depends on this: the skip check follows the wiki
        pages themselves.) See :func:`purge_section`.

        The seeded ``academic`` root is protected. The section is resolved
        case-insensitively against the dirs on disk, so the URL casing need not
        match exactly.
        """
        norm = normalize_section(section)
        if not norm or norm.lower() in _PROTECTED_SECTIONS:
            raise HTTPException(status_code=403, detail="This branch cannot be deleted.")
        match = next(
            (s for s in section_dirs(config) if s.lower() == norm.lower()), None
        )
        if match is None:
            raise HTTPException(status_code=404, detail=f"Section '{section}' not found.")
        purge_section(config, match)  # pages, ledger, cache, raw, overrides, vectors
        append_log(config, "section", match, detail="deleted via web UI")
        return {"section": match}

    @app.delete("/api/page/{slug}")
    def delete_page(
        slug: str,
        page_type: str = Query(..., alias="type"),
        section: str = Query(""),
    ) -> dict:
        """Delete one concept or source page thoroughly.

        The delete keys on slug **plus** type and section — a slug alone is
        ambiguous (a concept and a source can share one, and the same slug can
        live in several sections). Deleting a concept leaves the ingest ledger
        alone on purpose: the skip check follows the wiki pages, so the
        concept's source becomes re-ingestable. Deleting a source is a full
        teardown — its ledger record, normalized cache, and ``raw/`` bytes go
        with it, the slug is scrubbed from same-section concepts' ``sources:``
        provenance, and concepts left with no sources are deleted too (reported
        in the response). See :func:`purge_page`.
        """
        if page_type not in ("concept", "source"):
            raise HTTPException(status_code=422, detail="type must be 'concept' or 'source'")
        # source_path interpolates the slug into a filename verbatim — reject
        # anything that could escape the pages directory (covers percent-encoded
        # separators the route decodes back into the single path segment).
        if "/" in slug or "\\" in slug or slug in {".", ".."}:
            raise HTTPException(status_code=404, detail=f"no page with slug {slug!r}")
        norm = normalize_section(section)
        path = (
            concept_path(config, norm, slug)
            if page_type == "concept"
            else source_path(config, norm, slug)
        )
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"no {page_type} {slug!r} in section {norm or 'General'!r}",
            )
        result = purge_page(config, page_type, norm, slug)
        detail = "deleted via web UI"
        if result.scrubbed:
            detail += f"; provenance scrubbed: {', '.join(result.scrubbed)}"
        if result.removed_concepts:
            detail += f"; removed empty concepts: {', '.join(result.removed_concepts)}"
        append_log(config, "delete", f"{page_type} {slug}", detail=detail)
        return {
            "slug": slug,
            "type": page_type,
            "section": norm,
            "scrubbed": result.scrubbed,
            "removed_concepts": result.removed_concepts,
        }

    @app.get("/api/overrides")
    def overrides_list() -> dict:
        """Per-section status of the LLM instruction set plus the general defaults.

        Drives the customization UI: ``status`` shows, per component, which
        branches still use the general default (so an edit can be applied to
        several at once), and ``general`` carries the baseline text for each
        component. Sections come from the on-disk branches and any branch that
        already carries an override.
        """
        sections = sorted(section_dirs(config) | overrides.sections_with_overrides(config))
        return {
            "components": list(overrides.COMPONENTS),
            "general": {c: overrides.general_default(config, c) for c in overrides.COMPONENTS},
            "sections": [
                {"section": s, "label": _section_label(s), "status": overrides.override_status(config, s)}
                for s in sections
            ],
        }

    @app.get("/api/overrides/{section:path}")
    def overrides_get(section: str) -> dict:
        """The instruction set for one section: effective text, the override (or
        ``null`` when inherited), and the general default, per component."""
        norm = normalize_section(section)
        return {
            "section": norm,
            "label": _section_label(norm),
            "components": {
                c: {
                    "effective": overrides.effective(config, norm, c),
                    "override": overrides.read_override(config, norm, c),
                    "general": overrides.general_default(config, c),
                }
                for c in overrides.COMPONENTS
            },
        }

    @app.post("/api/overrides")
    def overrides_save(update: OverrideUpdate) -> dict:
        """Write/reset overrides across one or more sections (see OverrideUpdate)."""
        known = section_dirs(config) | overrides.sections_with_overrides(config)
        targets = []
        for raw in update.sections:
            norm = normalize_section(raw)
            if norm and norm not in known:
                raise HTTPException(status_code=404, detail=f"Section '{raw}' not found.")
            targets.append(norm)
        if not targets:
            raise HTTPException(status_code=422, detail="No target sections given.")
        try:
            for norm in targets:
                for component, text in update.set.items():
                    overrides.write_override(config, norm, component, text)
                for component in update.reset:
                    overrides.delete_override(config, norm, component)
        except ValueError as e:  # unknown component name
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {
            "updated": [
                {"section": s, "label": _section_label(s), "status": overrides.override_status(config, s)}
                for s in sorted(set(targets))
            ]
        }

    @app.get("/api/home")
    def home(section: str | None = None) -> dict:
        """The overview for ``section`` (the UI's current scope; default General).

        Each section hub's "Browse overview" lands here with its scope, so a
        course sees its own overview, a branch sees its branch overview, etc. The
        General root keeps its catalog fallback so a fresh vault's home isn't blank;
        a section with no overview yet returns empty (the UI shows an empty state).
        """
        norm = normalize_section(section or "")
        content = read_optional(overview_path(config, norm))
        if not content and not norm:
            content = read_optional(config.index_file)
        return {"title": "Overview", "content": content}

    @app.post("/api/overview/refresh")
    def overview_refresh(section: str = Body("", embed=True)) -> dict:
        """Regenerate one section's overview on demand (the hub's button / CLI).

        API-key-gated like ingest/query: the LLM rewrites the overview from the
        section's concept catalog. Unlike ingest (which also refreshes ancestors),
        this targets just the requested section — the user is on that hub.
        """
        if not _has_api_key(config):
            env = _api_key_env(config)
            raise HTTPException(
                status_code=503,
                detail=f"{env} is not set; set it and restart to regenerate overviews.",
            )
        provider = provider_factory(config)
        norm = normalize_section(section)
        try:
            path = refresh_overview(config, provider, norm)
        except ProviderError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        append_log(config, "overview", norm or "General", detail="regenerated via web UI")
        return {"section": norm, "content": read_optional(path)}

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
        hits = search(
            config,
            q,
            top_k=top_k or config.search_top_k,
            section=section,
            embedder=make_embedder(config),
        )
        return [
            {
                "slug": h.ref.slug,
                "title": h.ref.title,
                "section": h.ref.section,
                "score": round(h.score, 3),
            }
            for h in hits
        ]

    @app.post("/api/reindex")
    def reindex_endpoint() -> dict:
        """Rebuild the vector index from all concept pages (needs the search extra)."""
        embedder = make_embedder(config)
        if embedder is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Embeddings unavailable: set {config.embed_api_key_env} and "
                    "install the search extra (`pip install '.[search]'`)."
                ),
            )
        try:
            result = reindex_all(config, embedder)
        except VectorIndexUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except ProviderError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        append_log(
            config, "reindex", "vector index",
            detail=f"{result.pages} pages, {result.chunks} chunks embedded",
        )
        return {
            "pages": result.pages,
            "chunks": result.chunks,
            "skipped": result.skipped,
        }

    @app.post("/api/ingest")
    async def ingest_endpoint(
        file: UploadFile | None = File(None),
        url: str | None = Form(None),
        section: str | None = Form(None),
        prompt: str | None = Form(None),
    ) -> dict:
        """Ingest one uploaded file or URL into ``section`` (the UI's current scope).

        Mirrors ``llmwiki ingest``: the source is normalized, compiled into
        concept/source pages, and copied into ``raw/``. The UI always sends an
        explicit scope, so a missing/empty ``section`` means the General root
        (``""``) — never the configured default. The UI sends one request per
        selected file, all carrying the same scope.
        """
        if not _has_api_key(config):
            env = _api_key_env(config)
            raise HTTPException(
                status_code=503,
                detail=f"{env} is not set; set it and restart to ingest sources.",
            )
        spec_url = (url or "").strip()
        has_file = file is not None and bool(file.filename)
        if not spec_url and not has_file:
            raise HTTPException(status_code=422, detail="Provide a file or a URL to ingest.")
        # The General scope is "" — and empty multipart fields don't always survive
        # the wire — so collapse a missing/empty section to the root explicitly.
        target_section = section or ""
        # Optional free-text guidance steering how this source is compiled; blank
        # collapses to None so an un-guided ingest is unchanged.
        user_prompt = (prompt or "").strip() or None
        provider = provider_factory(config)
        try:
            if spec_url:
                result = ingest(
                    config, provider, spec_url, section=target_section, user_prompt=user_prompt
                )
            else:
                data = await file.read()  # type: ignore[union-attr]
                with tempfile.TemporaryDirectory() as td:
                    tmp = Path(td) / Path(file.filename).name  # type: ignore[union-attr]
                    tmp.write_bytes(data)
                    result = ingest(
                        config, provider, str(tmp), section=target_section, user_prompt=user_prompt
                    )
        except (LoaderError, ProviderError, ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {
            "status": result.status,
            "title": result.title,
            "source_slug": result.source_slug,
            "concept_slugs": result.concept_slugs,
            "reason": result.reason,
            "warnings": result.warnings,
            "section": target_section,
        }

    @app.post("/api/query")
    async def query_endpoint(
        question: str = Form(...),
        section: str | None = Form(None),
        files: list[UploadFile] = File(default=[]),
    ) -> dict:
        if not _has_api_key(config):
            env = _api_key_env(config)
            raise HTTPException(
                status_code=503,
                detail=f"{env} is not set; set it and restart to ask questions.",
            )
        provider = provider_factory(config)
        # Uploaded files are transient context for this one answer — loaded to
        # Markdown and handed to the model, never written to the wiki.
        attachments: list[tuple[str, str]] = []
        for f in files:
            if not f.filename:
                continue
            data = await f.read()
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / Path(f.filename).name
                tmp.write_bytes(data)
                try:
                    loaded = load_source(str(tmp), config=config, provider=provider)
                except LoaderError as e:
                    raise HTTPException(status_code=400, detail=str(e)) from e
            attachments.append((f.filename, loaded.markdown))
        try:
            result = answer(
                config, provider, question, section=section, attachments=attachments or None
            )
        except ProviderError as e:
            # The model call failed (timeout, rate limit, API error). Surface it as
            # a clean 503 instead of a 500 traceback so the Ask view can show it.
            raise HTTPException(status_code=503, detail=str(e)) from e
        return {
            "answer": result.answer,
            "pages_used": result.pages_used,
            "ungrounded": result.ungrounded,
        }

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
        try:
            issues = lint(config, provider=provider, deep=deep, section=section)
        except ProviderError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        return [{"level": i.level, "page": i.page, "message": i.message} for i in issues]

    # check_dir=False so create_app works before the frontend is built (tests,
    # fresh checkouts); requests simply 404 until `vite build` populates static/.
    app.mount("/", _SPAStaticFiles(directory=STATIC_DIR, html=True, check_dir=False), name="static")
    return app
