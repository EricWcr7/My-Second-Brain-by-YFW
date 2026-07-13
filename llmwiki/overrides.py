"""Per-section overrides for the LLM instruction set.

Every LLM operation is driven by an instruction *set*: the operation prompt plus
the wiki's purpose and schema. By default these come from one **general** source —
the packaged prompt files plus ``wiki/purpose.md`` and ``wiki/schema.md``. A
section may override any of them, so e.g. a proof-heavy course can carry
math-specific guidance while the rest of the knowledge base stays general.

Resolution is deliberately shallow: a section either has its **own** override file
for a component or it falls straight back to the general default — there is no
walking up ancestor sections. All IO here is deterministic (no LLM); the
pipelines call :func:`effective` to assemble their system prompts.

Layout under ``.llmwiki/`` (git-tracked, alongside ``config.toml``)::

    sections/<section-relpath>/<component>.md   # a section's override
    prompts/<op>.md                             # editable general op-prompt baseline

``purpose``/``schema`` have no packaged fallback; their general baseline is the
existing ``wiki/purpose.md`` / ``wiki/schema.md`` (empty string when absent).
"""

from __future__ import annotations

from pathlib import Path

from . import prompts
from .config import Config
from .store import ensure_dir
from .wiki import normalize_section, read_optional, section_to_relpath

# The operation prompts share their names with the packaged ``<op>.md``
# files; ``purpose``/``schema`` map to the wiki documents.
OPERATION_COMPONENTS = ("ingest_analysis", "ingest_generation", "answer", "lint", "solve")
DOC_COMPONENTS = ("purpose", "schema")
COMPONENTS = OPERATION_COMPONENTS + DOC_COMPONENTS


def _check_component(component: str) -> None:
    if component not in COMPONENTS:
        raise ValueError(f"unknown override component: {component!r}")


# --- general baseline --------------------------------------------------------


def _general_path(config: Config, component: str) -> Path:
    """The editable file holding a component's general baseline (may not exist)."""
    if component == "purpose":
        return config.purpose_file
    if component == "schema":
        return config.schema_file
    return config.prompt_overrides_dir / f"{component}.md"


def general_default(config: Config, component: str) -> str:
    """The general (section-independent) text for ``component``.

    Operation prompts fall back to the packaged template when no editable
    baseline file exists; ``purpose``/``schema`` are just the wiki files (``""``
    when absent), matching the previous ``read_optional`` behavior.
    """
    _check_component(component)
    text = read_optional(_general_path(config, component))
    if text.strip():
        return text
    if component in OPERATION_COMPONENTS:
        return prompts.load(f"{component}.md")
    return ""


# --- section overrides -------------------------------------------------------


def section_override_path(config: Config, section: str, component: str) -> Path | None:
    """Path to a section's override file, or ``None`` for the General root."""
    _check_component(component)
    section = normalize_section(section)
    if not section:
        return None
    return config.section_overrides_dir / section_to_relpath(section) / f"{component}.md"


def read_override(config: Config, section: str, component: str) -> str | None:
    """The section's override text, or ``None`` when it inherits the default."""
    path = section_override_path(config, section, component)
    if path is None or not path.exists():
        return None
    return path.read_text("utf-8")


def is_overridden(config: Config, section: str, component: str) -> bool:
    path = section_override_path(config, section, component)
    return path is not None and path.exists()


def effective(config: Config, section: str, component: str) -> str:
    """The instruction text actually used for ``component`` in ``section``."""
    override = read_override(config, section, component)
    return override if override is not None else general_default(config, component)


def override_status(config: Config, section: str) -> dict[str, str]:
    """Per-component status for the UI: ``"override"`` or ``"general"``."""
    return {
        c: "override" if is_overridden(config, section, c) else "general"
        for c in COMPONENTS
    }


def sections_with_overrides(config: Config) -> set[str]:
    """Normalized section paths that carry at least one override file.

    Lets a customized-but-empty branch (e.g. a seeded course with no pages yet)
    still appear in the customization UI alongside :func:`wiki.section_dirs`.
    """
    base = config.section_overrides_dir
    if not base.exists():
        return set()
    out: set[str] = set()
    for path in base.rglob("*.md"):
        if path.stem in COMPONENTS:
            out.add(normalize_section("/".join(path.parent.relative_to(base).parts)))
    out.discard("")
    return out


# --- writes ------------------------------------------------------------------


def write_override(config: Config, section: str, component: str, text: str) -> Path:
    """Set ``component`` for ``section``. The General root edits the baseline."""
    _check_component(component)
    section = normalize_section(section)
    path = section_override_path(config, section, component) if section else _general_path(
        config, component
    )
    ensure_dir(path.parent)
    path.write_text(text, "utf-8")
    return path


def delete_override(config: Config, section: str, component: str) -> bool:
    """Reset ``component`` back to the general default. Returns whether anything
    was removed.

    For the General root, only operation prompts have a deletable baseline file
    (resetting re-exposes the packaged default); ``purpose``/``schema`` *are* the
    baseline, so there is nothing to reset to and this is a no-op.
    """
    _check_component(component)
    section = normalize_section(section)
    if section:
        path = section_override_path(config, section, component)
    elif component in OPERATION_COMPONENTS:
        path = _general_path(config, component)
    else:
        return False
    if path is not None and path.exists():
        path.unlink()
        return True
    return False
