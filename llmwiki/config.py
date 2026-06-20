"""Configuration and vault paths.

A "vault" is the directory that holds ``raw/``, ``wiki/`` and ``.llmwiki/``.
Settings live in ``.llmwiki/config.toml``; API keys come from the environment
(``OPENAI_API_KEY`` or ``ANTHROPIC_API_KEY`` depending on ``provider``), never
from the config file.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

STATE_DIRNAME = ".llmwiki"


class ConfigError(Exception):
    """Raised when no vault is found or the config is invalid."""


@dataclass
class Config:
    root: Path
    # LLM backend: "openai" (default), or "anthropic"/"claude".
    provider: str = "openai"
    # Model IDs (exact, no date suffixes). None → the provider's own default,
    # so switching `provider` picks the right model family automatically.
    compile_model: str | None = None
    cheap_model: str | None = None
    # Section a source lands in when `--section` is omitted. Sections are
    # `/`-joined path strings (e.g. "academic/multivariable-calculus"); "" is the
    # General root that sees the whole knowledge base. Filing defaults to the flat
    # non-academic branch.
    default_section: str = "non-academic"
    # Retrieval / context budgets.
    search_top_k: int = 8
    context_token_budget: int = 60_000
    # If PyMuPDF text extraction yields fewer chars per page than this, the PDF
    # is treated as scanned/image-heavy and transcribed with a vision model.
    pdf_vision_min_chars_per_page: int = 100
    # Per-request resilience for provider calls: how long to wait before a call
    # times out (seconds) and how many times the SDK retries transient failures.
    request_timeout: float = 60.0
    max_retries: int = 2
    extra: dict = field(default_factory=dict)

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def sources_dir(self) -> Path:
        return self.raw_dir / "sources"

    @property
    def assets_dir(self) -> Path:
        return self.raw_dir / "assets"

    @property
    def wiki_dir(self) -> Path:
        return self.root / "wiki"

    @property
    def concepts_dir(self) -> Path:
        return self.wiki_dir / "concepts"

    @property
    def source_pages_dir(self) -> Path:
        return self.wiki_dir / "sources"

    @property
    def queries_dir(self) -> Path:
        return self.wiki_dir / "queries"

    @property
    def state_dir(self) -> Path:
        return self.root / STATE_DIRNAME

    @property
    def normalized_dir(self) -> Path:
        return self.state_dir / "normalized"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def config_file(self) -> Path:
        return self.state_dir / "config.toml"

    @property
    def section_overrides_dir(self) -> Path:
        # Per-section overrides of the LLM instruction set (one file per
        # component, mirroring the section path). See ``overrides.py``.
        return self.state_dir / "sections"

    @property
    def prompt_overrides_dir(self) -> Path:
        # Editable general-baseline operation prompts; shadow the packaged
        # defaults in ``prompts/`` when present.
        return self.state_dir / "prompts"

    @property
    def purpose_file(self) -> Path:
        return self.wiki_dir / "purpose.md"

    @property
    def schema_file(self) -> Path:
        return self.wiki_dir / "schema.md"

    @property
    def index_file(self) -> Path:
        return self.wiki_dir / "index.md"

    @property
    def log_file(self) -> Path:
        return self.wiki_dir / "log.md"

    @property
    def overview_file(self) -> Path:
        return self.wiki_dir / "overview.md"


# Keys that map directly onto Config fields when present in config.toml.
_SETTING_KEYS = (
    "provider",
    "compile_model",
    "cheap_model",
    "default_section",
    "search_top_k",
    "context_token_budget",
    "pdf_vision_min_chars_per_page",
    "request_timeout",
    "max_retries",
)


def find_vault_root(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` (default: cwd) to find a vault root."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / STATE_DIRNAME).is_dir():
            return candidate
    return None


def load_config(start: Path | None = None) -> Config:
    """Locate the vault and load ``.llmwiki/config.toml`` over the defaults."""
    root = find_vault_root(start)
    if root is None:
        raise ConfigError(
            "No llmwiki vault found here or in any parent directory. "
            "Run `llmwiki init` first."
        )
    cfg = Config(root=root)
    if cfg.config_file.exists():
        data = tomllib.loads(cfg.config_file.read_text("utf-8"))
        settings = data.get("settings", data)
        for key in _SETTING_KEYS:
            if key in settings:
                setattr(cfg, key, settings[key])
        cfg.extra = {k: v for k, v in settings.items() if k not in _SETTING_KEYS}
    return cfg
