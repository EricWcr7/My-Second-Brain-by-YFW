"""Filesystem state: checksums, the ingest ledger, and Markdown frontmatter IO."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from .config import Config


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# --- ingest ledger (.llmwiki/state.json) -------------------------------------


def load_state(config: Config) -> dict:
    if config.state_file.exists():
        return json.loads(config.state_file.read_text("utf-8"))
    return {"sources": {}}


def save_state(config: Config, state: dict) -> None:
    ensure_dir(config.state_dir)
    config.state_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), "utf-8"
    )


def get_source_record(state: dict, key: str) -> dict | None:
    return state.get("sources", {}).get(key)


def set_source_record(state: dict, key: str, record: dict) -> None:
    state.setdefault("sources", {})[key] = record


# --- Markdown pages with YAML frontmatter ------------------------------------


@dataclass
class Page:
    """A Markdown page split into frontmatter metadata and body content."""

    path: Path
    metadata: dict
    content: str


def read_page(path: Path) -> Page | None:
    if not path.exists():
        return None
    post = frontmatter.load(str(path))
    return Page(path=path, metadata=dict(post.metadata), content=post.content)


def write_page(path: Path, metadata: dict, content: str) -> None:
    ensure_dir(path.parent)
    post = frontmatter.Post(content, **metadata)
    path.write_text(frontmatter.dumps(post) + "\n", "utf-8")
