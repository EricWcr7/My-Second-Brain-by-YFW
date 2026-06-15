"""`llmwiki init`: create the vault layout and seed config/purpose/schema."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .store import ensure_dir
from .wiki import LOG_HEADER, rebuild_index

CONFIG_TOML = """\
# llmwiki configuration. API keys are NOT stored here — set the environment
# variable for your chosen provider (OPENAI_API_KEY or ANTHROPIC_API_KEY).
[settings]
# LLM backend: "openai" (default) or "anthropic".
provider = "openai"
# Model IDs are optional; leave unset to use the provider's defaults. OpenAI runs
# a GPT-5.5+ reasoning model at xhigh reasoning effort; Anthropic uses Claude Opus.
# (OpenAI: gpt-5.5 / gpt-5.5, Anthropic: claude-opus-4-8 / claude-haiku-4-5).
# compile_model = "gpt-5.5"        # ingest + answer model (must be gpt-5.5+)
# cheap_model = "gpt-5.5"          # reserved for cheap ops
# Section a source lands in when `--section` is omitted. Sections are `/`-joined
# paths (e.g. "academic/multivariable-calculus"); "" is the General root. Filing
# defaults to the flat non-academic branch.
default_section = "non-academic"
search_top_k = 8
context_token_budget = 60000
pdf_vision_min_chars_per_page = 100
"""

PURPOSE_MD = """\
# Purpose

This wiki is a personal **knowledge base** compiled from local materials. It is
not limited to academic or math content. The raw sources in `raw/` are the source
of truth; these wiki pages organize them for understanding, search, and review.

## Hierarchy & scope

Knowledge is organized as a **section hierarchy**. Every level runs the *same*
wiki operations (ingest, query, search, lint) — the only difference is **how much
of the knowledge base it can access**:

- **General** (root) — accesses the entire knowledge base.
  - **Non-academic** — personal, free-form knowledge; currently flat.
  - **Academic** — accesses all course knowledge.
    - one subsection per **course** — by default each accesses only its own
      knowledge. To widen, query a parent section (Academic or General).

A section is a `/`-joined path (e.g. `academic/multivariable-calculus`); a scope
sees a page when the scope is a prefix of the page's section.

## Goals (all sections)

- Preserve substance — never reduce material to shallow summaries; keep the
  detail, notation, and source references that make a page reusable.
- Make **relationships between concepts** explicit through `[[wikilinks]]` so the
  wiki reads as a connected map, not a pile of notes.
- Stay reliable and **citation-aware**: every claim should trace back to a source
  page, and every source page back to a raw file.

## Academic branch

Proof-heavy / theory-heavy courses (e.g. Multivariable Calculus, Statistical
Theory, Algorithms & Complexity) live under `academic/<course>`. For these:

- Preserve **definitions, theorems, assumptions, notation, formulas, proof ideas,
  and examples** faithfully, with all mathematics as LaTeX.
- **Keep all Theorem/Lemma/Example/Remark codes** and put the code first, e.g.
  "Theorem 2.1.1: {content}".
- **Place section/subsection codes (e.g. Section 2.1, Subsection 2.1.1) as tags**,
  in valid Obsidian tag format.

## Non-academic branch

Notes, references, and free-form knowledge live under `non-academic`. Keep them
citation-aware and wikilinked, but they need not follow the academic page schema.
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

## Concept pages (`wiki/concepts/<section>/<slug>.md`)

Frontmatter:

```yaml
title: <human title>
type: concept
section: <section path>          # e.g. academic/multivariable-calculus
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

## Source pages (`wiki/sources/<section>/<slug>.md`)

Frontmatter:

```yaml
title: <human title>
type: source
section: <section path>          # e.g. academic/multivariable-calculus
kind: <markdown|pdf|docx|pptx|image|web|text>
path: <relative path under raw/ , or the URL>
assets: [<relative path under raw/assets/>, ...]   # optional; image sources only
ingested: <YYYY-MM-DD>
```

Body — a structured summary of the source plus a list of the concepts it grounds
(as `[[wikilinks]]`). Image sources additionally embed the captured asset with
`![title](relative/path)` so it is viewable.

## Maintenance files

- `index.md` — auto-generated navigation catalog (do not edit by hand).
- `log.md` — append-only operation record; each entry is a
  `## [YYYY-MM-DD] <op> | <title>` heading so the timeline is greppable.
- `overview.md` — narrative orientation across sections (compiler-maintained).
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

    # Seed the conventional top-level branches so the hierarchy is visible from
    # the start. These are conventions, not enforced — any nesting depth works.
    for base in (config.concepts_dir, config.source_pages_dir):
        for branch in ("academic", "non-academic"):
            ensure_dir(base / branch)

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
        config.log_file.write_text(LOG_HEADER, "utf-8")
    rebuild_index(config)

    # Keep tool state out of version control.
    gitignore = config.state_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("normalized/\nstate.json\n", "utf-8")

    return config
