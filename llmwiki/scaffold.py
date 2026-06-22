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
# a GPT-5.5+ reasoning model at high reasoning effort; Anthropic uses Claude Opus.
# (OpenAI: gpt-5.5 / gpt-5.5, Anthropic: claude-opus-4-8 / claude-haiku-4-5).
# compile_model = "gpt-5.5"        # ingest + answer model (must be gpt-5.5+)
# cheap_model = "gpt-5.5"          # reserved for cheap ops
# Section a source lands in when `--section` is omitted. Sections are `/`-joined
# paths (e.g. "academic/multivariable-calculus"); "" is the General root. Filing
# defaults to the flat non-academic branch.
default_section = "non-academic"
search_top_k = 8
context_token_budget = 60000
# rerank = true                      # opt-in: LLM reranks retrieved pages (one extra call per Ask)
# rerank_candidates = 20             # pages pulled before reranking down to search_top_k
pdf_vision_min_chars_per_page = 100
pdf_vision_batch_pages = 10          # vision-transcribe a scanned PDF this many pages per call
pdf_vision_max_concurrency = 4       # how many of those batch calls to run at once
# Provider call resilience: seconds before a request times out, and how many
# times the SDK retries transient failures (rate limits, dropped connections).
# Generous by default — ingesting a large source runs a reasoning model that can
# take minutes.
request_timeout = 300.0
ingest_request_timeout = 3600.0      # longer ceiling for ingest only (big/multi-pass sources)
max_retries = 2
"""

PURPOSE_MD = """\
# Purpose

This wiki is a personal **knowledge base** compiled from local materials — notes,
articles, documents, and images. The raw sources in `raw/` are the source of
truth; these wiki pages organize them for understanding, search, and review.

## Hierarchy & scope

Knowledge is organized as a **section hierarchy**. Every level runs the *same*
wiki operations (ingest, query, search, lint) — the only difference is **how much
of the knowledge base it can access**:

- **General** (root) — accesses the entire knowledge base.
  - **Non-academic** — personal, free-form knowledge; currently flat.
  - **Academic** — accesses all course knowledge.
    - one subsection per **course** — by default each accesses only its own
      knowledge. To widen, query a parent section (Academic or General).

A section is a `/`-joined path (e.g. `academic/example-course`); a scope sees a page when
the scope is a prefix of the page's section.

## Goals (all sections)

- Preserve substance — never reduce material to shallow summaries; keep the
  detail, specifics, and source references that make a page reusable.
- Make **relationships between concepts** explicit through `[[wikilinks]]` so the
  wiki reads as a connected map, not a pile of notes.
- Stay reliable and **citation-aware**: every claim should trace back to a source
  page, and every source page back to a raw file.

## Per-section customization

These instructions are the **general default**. Any branch may carry its own
purpose, schema, or per-operation prompts that replace this default for that
branch — e.g. a proof-heavy course can require theorems, proof ideas, and LaTeX
notation while the rest of the wiki stays general. Customize a branch from its hub
in the web app.
"""

SCHEMA_MD = """\
# Schema

Conventions every generated page MUST follow. These instructions are read by the
compiler at ingest and query time.

## Format

- Obsidian-compatible Markdown.
- Link to other concepts/sources with `[[slug]]` or `[[slug|Display Text]]`.
- Write any mathematics as LaTeX (inline `$...$`, display `$$...$$`) and code in
  fenced blocks. Preserve the notation and wording used in the source.
- Every page begins with YAML frontmatter.

## Concept pages (`wiki/concepts/<section>/<slug>.md`)

Frontmatter:

```yaml
title: <human title>
type: concept
section: <section path>          # e.g. non-academic/productivity
tags: [<topic>, ...]
aliases: [<alternate names>, ...]
sources: [<source-slug>, ...]   # provenance — required, never empty
updated: <YYYY-MM-DD>
```

Body — include only the sections that apply, in this order:

- **Summary** — what the concept is, in a sentence or two.
- **Details** — the substance: key facts, explanation, context, and specifics.
- **Key points** — notable specifics worth surfacing (bullets).
- **Examples** — concrete examples or instances, when helpful.
- **Related** — `[[wikilinks]]` to connected concepts, with a phrase on how they
  relate (e.g. "builds on [[spaced-repetition]]").
- **Sources** — `[[source-slug]]` links the claims draw from.

## Source pages (`wiki/sources/<section>/<slug>.md`)

Frontmatter:

```yaml
title: <human title>
type: source
section: <section path>          # e.g. non-academic/productivity
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
