# My-Second-Brain-by-YFW

A local-first **academic LLM Wiki**. `llmwiki` compiles local course materials
(Markdown, PDFs, slides, Word docs, images, web URLs) into a persistent,
Obsidian-compatible Markdown study wiki. Raw sources stay local and remain the
source of truth; the generated `wiki/` pages are an editable, citation-aware
study layer for proof-heavy courses.

- **Concept-centric**: one page per concept (definition, theorems, assumptions,
  notation, formulas, proof ideas, examples) plus one page per source.
- **Obsidian-native**: `[[wikilinks]]`, YAML frontmatter, `$…$`/`$$…$$` math.
- **No vectors / no cloud / single-user.** Keyword search + an LLM compiler.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # add [dev] for the test suite
export ANTHROPIC_API_KEY=""
```

## Quick start

```bash
llmwiki init                                   # scaffold raw/, wiki/, .llmwiki/
llmwiki ingest examples/sample_calculus.md --course "Multivariable Calculus"
llmwiki ingest https://en.wikipedia.org/wiki/Gradient --course "Multivariable Calculus"
llmwiki query "state the multivariable chain rule and the proof idea"
llmwiki search "chain rule"                     # keyword search, no LLM
llmwiki lint                                     # structural checks
llmwiki lint --deep                              # + LLM contradiction/gap review
```

Open the resulting `wiki/` folder in Obsidian to read, search, graph, and edit.

## Layout

| Path            | Role                                                        |
| --------------- | ---------------------------------------------------------- |
| `raw/`          | Source of truth — your dropped files (never edited).        |
| `wiki/`         | Generated study layer: `concepts/`, `sources/`, `index.md`. |
| `.llmwiki/`     | Tool state: `config.toml`, `state.json`, normalized cache.  |
| `llmwiki/`      | The Python package (the tool).                              |

## Commands

- `init [path]` — create a vault.
- `ingest <path|url> [--course] [--vision] [--force]` — compile a source.
- `query "<question>" [--course] [--save]` — answer from the wiki, with citations.
- `search "<keywords>" [--course] [--top-k N]` — keyword ranking only.
- `lint [--course] [--deep]` — find dangling links, missing provenance, etc.

## Tests

```bash
pytest        # unit tests; the LLM is mocked, no API key required
```

Configuration lives in `.llmwiki/config.toml` (models, default course, budgets).
API keys are read from the environment, never stored in the vault.
