"""Shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llmwiki.config import Config  # noqa: E402
from llmwiki.scaffold import scaffold_vault  # noqa: E402


@pytest.fixture
def vault(tmp_path) -> Config:
    """A freshly scaffolded vault rooted at a temp dir."""
    return scaffold_vault(tmp_path)
