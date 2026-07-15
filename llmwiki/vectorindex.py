"""On-disk vector index (LanceDB), deterministic IO — vectors are passed IN.

No LLM call lives here: the embedding happens in :mod:`embeddings`, and this module
only persists/queries the resulting vectors. The table is named after the embedding
model (``chunks__<model-slug>``) so that changing the global ``embed_model`` lands
chunks in a fresh, correctly-dimensioned table (a LanceDB vector column is
fixed-dimension) rather than colliding with old vectors; ``reindex`` repopulates it.
Each page replacement uses a LanceDB transaction, keyed by a section-qualified
chunk id, so failed writes preserve the previous healthy rows and same-slug
concepts in sibling sections do not overwrite one another. A duplicate-id repair
uses one table-overwrite commit because merge joins require unique target ids.

LanceDB is an optional dependency (the ``[search]`` extra). When it is not
installed, :func:`open_index` raises :class:`VectorIndexUnavailable` and callers
degrade to BM25-only retrieval.
"""

from __future__ import annotations

from collections import Counter
import re
import threading

from .config import Config
from .store import ensure_dir


class VectorIndexUnavailable(Exception):
    """Raised when the LanceDB-backed index cannot be used (dep missing, etc.)."""


class DuplicateChunkIDsError(RuntimeError):
    """Stored chunk ids are not unique, so a dict snapshot would be lossy."""


def model_table_name(model: str) -> str:
    """Stable LanceDB table name for an embedding model id."""
    return "chunks__" + re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-").lower()


def _import_lancedb():
    try:
        import lancedb
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise VectorIndexUnavailable(
            "LanceDB is not installed. From the repository root, reinstall with "
            "the search extra: `pip install '.[search]'`."
        ) from e
    return lancedb


# Columns persisted per chunk (the embedding goes in ``vector``).
ROW_FIELDS = ("id", "page_slug", "section", "page_title", "heading", "content_hash")
VECTOR_INDEX_WRITE_LOCK = threading.RLock()


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _page_predicate(section: str, page_slug: str) -> str:
    return (
        f"section = {_sql_string(section)} AND "
        f"page_slug = {_sql_string(page_slug)}"
    )


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

    def upsert_page(
        self, model: str, section: str, page_slug: str, rows: list[dict]
    ) -> None:
        """Atomically replace one section-qualified page's chunks with ``rows``.

        ``rows`` are dicts of :data:`ROW_FIELDS` plus a ``vector`` list. Empty
        ``rows`` just clears the page's existing chunks (used when a page is gone).
        """
        with VECTOR_INDEX_WRITE_LOCK:
            source_ids = [row["id"] for row in rows]
            if len(source_ids) != len(set(source_ids)):
                raise ValueError("Replacement rows contain duplicate chunk ids.")
            name = model_table_name(model)
            if name in self._table_names():
                table = self.db.open_table(name)
                predicate = _page_predicate(section, page_slug)
                if rows:
                    current = table.to_arrow().to_pylist()
                    counts = Counter(row["id"] for row in current)
                    page_ids = {
                        row["id"]
                        for row in current
                        if row["section"] == section
                        and row["page_slug"] == page_slug
                    }
                    conflicted_ids = page_ids | set(source_ids)
                    if any(counts[chunk_id] > 1 for chunk_id in conflicted_ids):
                        # Merge-join behavior is undefined when the target id is
                        # duplicated. Replace the table in one Lance commit, keeping
                        # every unrelated row and exactly one fresh copy of this page.
                        replacement = [
                            row
                            for row in current
                            if not (
                                row["section"] == section
                                and row["page_slug"] == page_slug
                            )
                            and row["id"] not in source_ids
                        ]
                        replacement.extend(rows)
                        # ``mode="overwrite"`` otherwise infers a fresh schema and
                        # could silently accept a different vector dimension. Bind
                        # the replacement to the current fixed-size vector schema
                        # before the commit so a malformed repair leaves it intact.
                        import pyarrow as pa

                        try:
                            replacement_table = pa.Table.from_pylist(
                                replacement, schema=table.schema
                            )
                        except (TypeError, ValueError) as error:
                            raise ValueError(
                                "Replacement rows do not match the existing "
                                "vector index schema."
                            ) from error
                        table.add(
                            replacement_table,
                            mode="overwrite",
                            on_bad_vectors="error",
                        )
                    else:
                        (
                            table.merge_insert("id")
                            .when_matched_update_all()
                            .when_not_matched_insert_all()
                            .when_not_matched_by_source_delete(predicate)
                            .execute(rows, on_bad_vectors="error")
                        )
                else:
                    table.delete(predicate)
            elif rows:
                self.db.create_table(name, data=rows)

    def delete_pages(self, pages: set[tuple[str, str]]) -> None:
        """Remove section-qualified pages from every model table."""
        if not pages:
            return
        predicate = " OR ".join(
            f"({_page_predicate(section, slug)})" for section, slug in sorted(pages)
        )
        with VECTOR_INDEX_WRITE_LOCK:
            for name in self._table_names():
                self.db.open_table(name).delete(predicate)

    # --- reads ---------------------------------------------------------------

    def existing_hashes(self, model: str) -> dict[str, str]:
        """``chunk id -> content_hash`` for ``model``'s table (incremental reindex)."""
        return {
            chunk_id: row["content_hash"]
            for chunk_id, row in self.existing_records(model).items()
        }

    def existing_records(self, model: str) -> dict[str, dict]:
        """``chunk id -> metadata`` snapshot used for incremental reconciliation."""
        rows = self.metadata_rows(model)
        records = {row["id"]: row for row in rows}
        if len(records) != len(rows):
            counts = Counter(row["id"] for row in rows)
            duplicates = sorted(chunk_id for chunk_id, n in counts.items() if n > 1)
            raise DuplicateChunkIDsError(
                f"Vector index contains {len(duplicates)} duplicate chunk id(s)."
            )
        return records

    def metadata_rows(self, model: str) -> list[dict]:
        """Metadata rows without collapsing duplicate chunk ids."""
        return [
            {field: row[field] for field in ROW_FIELDS}
            for row in self.rows(model)
        ]

    def stored_pages(self, model: str) -> set[tuple[str, str]]:
        """Section-qualified page identities currently present in ``model``."""
        return {
            (row["section"], row["page_slug"])
            for row in self.metadata_rows(model)
        }

    def rows(self, model: str) -> list[dict]:
        """Raw rows for integrity checks and tests; returns an empty list if absent."""
        name = model_table_name(model)
        if name not in self._table_names():
            return []
        return self.db.open_table(name).to_arrow().to_pylist()

    def search(self, model: str, query_vec: list[float], limit: int) -> list[dict]:
        """Top-``limit`` chunk rows nearest to ``query_vec`` in ``model``'s table,
        returned nearest-first. Carries :data:`ROW_FIELDS` plus ``_distance`` (the
        metadata only — the embedding column is not pulled back)."""
        with VECTOR_INDEX_WRITE_LOCK:
            name = model_table_name(model)
            if name not in self._table_names():
                return []
            tbl = self.db.open_table(name)
            # Include ``_distance`` in the projection: it is implicitly added today,
            # and naming it explicitly keeps that stable and silences LanceDB's
            # autoprojection deprecation warning.
            return (
                tbl.search(query_vec)
                .select([*ROW_FIELDS, "_distance"])
                .limit(limit)
                .to_list()
            )


def open_index(config: Config) -> VectorIndex:
    """Open the vector index, or raise :class:`VectorIndexUnavailable`."""
    return VectorIndex(config)
