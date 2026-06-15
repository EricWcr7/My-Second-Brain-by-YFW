"""`llmwiki init`: create the vault layout and seed config/purpose/schema."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .store import ensure_dir
from .wiki import rebuild_index

CONFIG_TOML = """\
# llmwiki configuration. API keys are NOT stored here — set ANTHROPIC_API_KEY
# in your environment.
[settings]
compile_model = "claude-opus-4-8"
cheap_model = "claude-haiku-4-5"
default_course = "General"
search_top_k = 8
context_token_budget = 60000
pdf_vision_min_chars_per_page = 100
"""

PURPOSE_MD = """\
# Purpose

This wiki is a personal **academic study layer** compiled from local course
materials. The raw sources in `raw/` are the source of truth; these wiki pages
organize them for understanding, search, and review.

## Goals

- Preserve academic substance: **definitions, theorems, assumptions, notation,
  formulas, proof ideas, examples, and source references** — never reduce
  material to shallow summaries.
- Make sure you **keep all the Theorem/Lemma/Example/Remark codes** when you
  generate the wiki pages from the ingested textbook. In addition, please put
  the codes as the starter, like "Theorem 2.1.1: {content}".
- Please **place section and subsection codes (e.g., Section 2.1,
  Subsection 2.1.1, etc.) as a tag.** Please keep in mind that
  your tag must be in the vaid format for Obsidian.
- Make **relationships between concepts** explicit through `[[wikilinks]]` so
  the wiki reads as a connected map, not a pile of notes.
- Stay reliable and **citation-aware**: every claim should trace back to a
  source page, and every source page back to a raw file.

## Courses

Proof-heavy / theory-heavy courses are the primary focus, e.g.:

- Multivariable Calculus
- Statistical Theory
- Algorithms & Complexity

Each ingested source is tagged with a `course`, and pages are foldered by course.
"""

SCHEMA_MD = """\
# Schema

Conventions every generated page MUST follow. These instructions are read by the
compiler at ingest and query time.

## Format

- Obsidian-compatible Markdown.
- Link to other concepts/sources with `[[slug]]` or `[[slug|Display Text]]`.
- Write all mathematics as LaTeX: inline `$...$`, display `$$...$$`. Preserve the
  notation used in the source.
- Every page begins with YAML frontmatter.

## Concept pages (`wiki/concepts/<course>/<slug>.md`)

Frontmatter:

```yaml
title: <human title>
type: concept
course: <course name>
tags: [<topic>, ...]
aliases: [<alternate names>, ...]
sources: [<source-slug>, ...]   # provenance — required, never empty
updated: <YYYY-MM-DD>
```

Body — include only the sections that apply, in this order:

- **Definition** — precise statement of what the concept is.
- **Assumptions / Hypotheses** — conditions under which results hold.
- **Statement** — theorem/lemma/proposition statements (verbatim-faithful).
- **Notation** — symbols and their meaning.
- **Key Formulas** — important equations in LaTeX.
- **Proof idea / sketch** — the essential argument, not necessarily full rigor.
- **Examples** — worked or illustrative examples.
- **Related** — `[[wikilinks]]` to connected concepts, with a phrase on how they
  relate (e.g. "generalizes [[gradient]]").
- **Sources** — `[[source-slug]]` links the claims draw from.

## Source pages (`wiki/sources/<course>/<slug>.md`)

Frontmatter:

```yaml
title: <human title>
type: source
course: <course name>
kind: <markdown|pdf|docx|pptx|image|web|text>
path: <relative path under raw/ , or the URL>
ingested: <YYYY-MM-DD>
```

Body — a structured summary of the source plus a list of the concepts it grounds
(as `[[wikilinks]]`).

## Maintenance files

- `index.md` — auto-generated navigation catalog (do not edit by hand).
- `log.md` — append-only operation record.
- `overview.md` — narrative orientation across courses (compiler-maintained).
"""

OVERVIEW_MD = """\
# Overview

A high-level orientation to what this wiki covers. This page is refreshed as new
sources are ingested.

_Empty — ingest some sources to build the overview._
"""


def scaffold_vault(root: Path) -> Config:
    """Create directories and seed files. Idempotent: never overwrites content."""
    config = Config(root=root)

    for d in (
        config.sources_dir,
        config.assets_dir,
        config.concepts_dir,
        config.source_pages_dir,
        config.queries_dir,
        config.normalized_dir,
    ):
        ensure_dir(d)

    seeds = {
        config.config_file: CONFIG_TOML,
        config.purpose_file: PURPOSE_MD,
        config.schema_file: SCHEMA_MD,
        config.overview_file: OVERVIEW_MD,
    }
    for path, text in seeds.items():
        if not path.exists():
            ensure_dir(path.parent)
            path.write_text(text, "utf-8")

    if not config.log_file.exists():
        config.log_file.write_text(
            "# Log\n\nChronological record of wiki operations.\n\n", "utf-8"
        )
    rebuild_index(config)

    # Keep tool state out of version control.
    gitignore = config.state_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("normalized/\nstate.json\n", "utf-8")

    return config
