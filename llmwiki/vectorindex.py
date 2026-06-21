"""On-disk vector index (LanceDB), deterministic IO — vectors are passed IN.

No LLM call lives here: the embedding happens in :mod:`embeddings`, and this module
only persists/queries the resulting vectors. The table is named after the embedding
model (``chunks__<model-slug>``) so that changing the global ``embed_model`` lands
chunks in a fresh, correctly-dimensioned table (a LanceDB vector column is
fixed-dimension) rather than colliding with old vectors; ``reindex`` repopulates it.

LanceDB is an optional dependency (the ``[search]`` extra). When it is not
installed, :func:`open_index` raises :class:`VectorIndexUnavailable` and callers
degrade to BM25-only retrieval.
"""

from __future__ import annotations

import re

from .config import Config
from .store import ensure_dir


class VectorIndexUnavailable(Exception):
    """Raised when the LanceDB-backed index cannot be used (dep missing, etc.)."""


def model_table_name(model: str) -> str:
    """Stable LanceDB table name for an embedding model id."""
    return "chunks__" + re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-").lower()


def _import_lancedb():
    try:
        import lancedb
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise VectorIndexUnavailable(
            "LanceDB is not installed. Install the search extra: "
            "`pip install 'llmwiki[search]'`."
        ) from e
    return lancedb


# Columns persisted per chunk (the embedding goes in ``vector``).
ROW_FIELDS = ("id", "page_slug", "section", "page_title", "heading", "content_hash")


class VectorIndex:
    def __init__(self, config: Config):
        self._lancedb = _import_lancedb()
        ensure_dir(config.lancedb_dir)
        self.db = self._lancedb.connect(str(config.lancedb_dir))

    def _table_names(self) -> list[str]:
        # ``list_tables`` is the current API (returns a response object whose
        # ``.tables`` holds the names); ``table_names`` is the older list alias.
        lister = getattr(self.db, "list_tables", None)
        if lister is None:
            return list(self.db.table_names())
        res = lister()
        return list(getattr(res, "tables", res))

    # --- writes --------------------------------------------------------------

    def upsert_page(self, model: str, page_slug: str, rows: list[dict]) -> None:
        """Replace every chunk for ``page_slug`` in ``model``'s table with ``rows``.

        ``rows`` are dicts of :data:`ROW_FIELDS` plus a ``vector`` list. Empty
        ``rows`` just clears the page's existing chunks (used when a page is gone).
        """
        name = model_table_name(model)
        if name in self._table_names():
            tbl = self.db.open_table(name)
            tbl.delete(f"page_slug = '{page_slug}'")
            if rows:
                tbl.add(rows)
        elif rows:
            self.db.create_table(name, data=rows)

    def delete_page_slugs(self, slugs: set[str]) -> None:
        """Remove the given page slugs from every model table (deletion cascade)."""
        if not slugs:
            return
        predicate = " OR ".join(f"page_slug = '{s}'" for s in sorted(slugs))
        for name in self._table_names():
            self.db.open_table(name).delete(predicate)

    # --- reads ---------------------------------------------------------------

    def existing_hashes(self, model: str) -> dict[str, str]:
        """``chunk id -> content_hash`` for ``model``'s table (incremental reindex)."""
        name = model_table_name(model)
        if name not in self._table_names():
            return {}
        rows = self.db.open_table(name).to_arrow().to_pylist()
        return {r["id"]: r["content_hash"] for r in rows}

    def search(self, model: str, query_vec: list[float], limit: int) -> list[dict]:
        """Top-``limit`` chunk rows nearest to ``query_vec`` in ``model``'s table,
        returned nearest-first. Carries :data:`ROW_FIELDS` plus ``_distance`` (the
        metadata only — the embedding column is not pulled back)."""
        name = model_table_name(model)
        if name not in self._table_names():
            return []
        tbl = self.db.open_table(name)
        # Include ``_distance`` in the projection: it is implicitly added today, and
        # naming it explicitly keeps that stable and silences LanceDB's autoprojection
        # deprecation warning.
        return (
            tbl.search(query_vec)
            .select([*ROW_FIELDS, "_distance"])
            .limit(limit)
            .to_list()
        )


def open_index(config: Config) -> VectorIndex:
    """Open the vector index, or raise :class:`VectorIndexUnavailable`."""
    return VectorIndex(config)
