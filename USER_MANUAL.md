# User Manual

A task-oriented guide to `llmwiki` — what you can do with it and how to do each
thing properly. For installation, configuration keys, and troubleshooting, see
the [README](README.md); this manual focuses on **use cases and workflows**.

> Keep this manual current. When the project's commands, flags, operations,
> config, page formats, or supported sources change, update the matching section
> here (and the command cheat-sheet) so the manual never drifts from the tool.

---

## 1. The mental model

`llmwiki` turns a pile of local materials into a maintained, interlinked
Markdown wiki. The division of labor is the whole point:

- **You** curate sources, ask questions, and decide what matters.
- **The LLM** writes and maintains the entire `wiki/` layer — every page,
  summary, cross-reference, and index entry. You almost never hand-edit wiki
  pages.

Three layers, which you should never confuse:

| Layer | What it is | Who edits it |
| ----- | ---------- | ------------ |
| **Raw sources** (`raw/`) | The files you ingest, copied in verbatim. The source of truth. | You (by ingesting). Immutable afterwards. |
| **Wiki** (`wiki/`) | LLM-generated concept/source pages, plus `index.md`, `log.md`, `overview.md`. | The LLM. |
| **Schema** (`wiki/purpose.md`, `wiki/schema.md`) | The instructions the compiler obeys. | You + the LLM, occasionally. |

Unlike classic RAG (which re-reads raw chunks on every question), the knowledge
is **compiled once and kept current**. Cross-references and contradictions are
already resolved on the page, so answers compound over time.

---

## 2. Core concepts you need before starting

### The vault
A "vault" is any directory containing a `.llmwiki/` folder. Commands walk upward
from your current directory to find it, so run them anywhere inside the vault.

### Sections and scope
Knowledge is a tree of **sections**. A section is a `/`-joined path
(e.g. `academic/multivariable-calculus`); the empty path `""` is the **General**
root.

```
General (root)            → sees the ENTIRE knowledge base
├── non-academic (flat)   → only non-academic knowledge
└── academic              → all courses
    └── academic/<course> → only that course
```

Every operation takes an optional `--section` and obeys one **prefix rule**: a
scope sees a page if and only if the scope is a prefix of the page's section.
General sees everything; `academic` sees every course; `academic/calc` sees only
itself. To **widen** a course query, point it at a parent section. There is no
separate "share" mechanism — scope *is* access.

`academic` / `non-academic` are just seeded conventions; any depth works. Add a
course by ingesting into it (`--section academic/<new-course>`).

### Page types (all under `wiki/`, all LLM-owned)
| Page | Purpose |
| ---- | ------- |
| `concepts/<section>/<slug>.md` | One concept: definition, theorems, notation, formulas, proof ideas, examples. |
| `sources/<section>/<slug>.md` | One ingested source: summary + the concepts it grounds. |
| `queries/<slug>.md` | An answer you saved with `query --save`. |
| `index.md` | Auto-regenerated navigation catalog. **Never hand-edit.** |
| `log.md` | Append-only, greppable operation timeline. **Never hand-edit.** |
| `overview.md` | Narrative orientation, refreshed on ingest. |
| `purpose.md`, `schema.md` | The schema layer, fed into every LLM call. |

### Provenance
Every concept page carries a `sources:` list tracing back to a source page, which
traces back to a raw file. `lint` enforces this. It's what makes answers
trustworthy and auditable.

---

## 3. Getting set up (quick recap)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install ".[dev]"                 # add ".[web]" for the browser UI
export OPENAI_API_KEY=sk-...         # or ANTHROPIC_API_KEY if provider="anthropic"
```

A key is needed only for `ingest`, `query`, and `lint --deep`. `init`, `search`,
and plain `lint` work offline. Full details (key persistence, hardened install,
provider switch) are in [README §1–3](README.md#1-requirements).

---

## 4. Use cases

Each use case is a realistic workflow with the exact commands and what to expect.

### UC1 — Start a new knowledge base
```bash
cd ~/my-knowledge
llmwiki init
```
Creates `raw/`, `wiki/` (seeded `purpose.md` / `schema.md` / `overview.md` /
`index.md` / `log.md`), and `.llmwiki/`. Idempotent and offline — it never
overwrites existing content. Open the folder in Obsidian or just start ingesting.

### UC2 — Build up a course (academic branch)
Ingest course materials one at a time, staying in the loop:
```bash
llmwiki ingest ~/Downloads/lecture3.pdf --section academic/multivariable-calculus
llmwiki ingest ~/Downloads/lecture4.pdf --section academic/multivariable-calculus
```
Each ingest writes/merges concept pages, writes the source page, refreshes
`overview.md`, regenerates `index.md`, and appends a `log.md` entry. Re-ingesting
an edited file **merges** new material into the existing concept pages rather than
duplicating them.

Then study by asking:
```bash
llmwiki query "state the chain rule and its proof idea" --section academic/multivariable-calculus
```

For proof-heavy courses the schema preserves definitions, theorem codes,
notation, and LaTeX math faithfully — see `wiki/purpose.md`.

### UC3 — Personal / free-form knowledge (non-academic branch)
`non-academic` is the default section, so you can omit `--section`:
```bash
llmwiki ingest ~/Downloads/article.md
llmwiki ingest https://example.com/blog-post
llmwiki query "what have I read about habit formation?"
```
Non-academic pages stay citation-aware and wikilinked but don't follow the strict
academic page schema.

### UC4 — Ingest any supported source type
| Source | Command | Notes |
| ------ | ------- | ----- |
| Markdown / text | `llmwiki ingest notes.md` | Fastest path; no vision. |
| Text PDF | `llmwiki ingest paper.pdf` | Text extracted with PyMuPDF. |
| Scanned / math PDF | `llmwiki ingest scanned.pdf --vision` | Forces vision transcription (auto-triggers below `pdf_vision_min_chars_per_page`). |
| Word | `llmwiki ingest report.docx` | |
| PowerPoint | `llmwiki ingest deck.pptx` | |
| Image | `llmwiki ingest diagram.png` | Transcribed by vision **and** the file is copied into `raw/assets/`, embedded in the source page, and recorded under `assets:` provenance. |
| Web URL | `llmwiki ingest https://…` | Fetched and cleaned to Markdown. |

Useful flags: `--force` re-ingests an unchanged file (sources are SHA256-skipped
by default); `--section` files it into a branch.

### UC5 — Ask questions and let answers compound
A basic question (answered only from the wiki, with citations):
```bash
llmwiki query "compare the gradient and the directional derivative" --section academic
```
Save a good answer back into the wiki so it accumulates like a source:
```bash
llmwiki query "compare gradient vs directional derivative" --section academic --save
```
This writes `wiki/queries/<slug>.md` and journals it to `log.md`.

Choose the answer's shape with `--format` (all text-only):
```bash
llmwiki query "compare three integration techniques" --format table   # Markdown comparison table
llmwiki query "summarize the unit for a study deck" --format slides    # Marp slide deck
```
A saved `slides` answer gets a `marp: true` frontmatter flag so Obsidian's Marp
plugin renders it as a deck. (`prose` is the default.)

### UC6 — Fast keyword search (no LLM, no key)
```bash
llmwiki search "chain rule" --section academic --top-k 10
```
BM25-lite ranking over concept pages. Instant and free — use it to locate pages
before asking a full question, or when you don't need synthesis.

### UC7 — Health-check and grow the wiki
Structural checks (offline):
```bash
llmwiki lint
```
Flags missing `sources:` provenance (error), unresolved source references,
dangling `[[wikilinks]]`, and orphan pages.

Deep review (needs a key) adds an LLM pass:
```bash
llmwiki lint --deep
```
Beyond contradictions / missing concepts / stale-or-unclear claims, the deep pass
**suggests growth**: missing cross-references, new questions to investigate,
sources to seek, and data gaps a web search could fill. These are suggestions —
the tool does not browse the web itself. Both runs append a one-line summary to
`log.md`. A non-zero exit code means an `error`-level issue exists (handy in CI).

### UC8 — Read and navigate in Obsidian
Open the `wiki/` folder as an Obsidian vault. You get:
- **Graph view** — see hubs, clusters, and orphan pages at a glance.
- **`[[wikilinks]]`** — click through related concepts and back to sources.
- **Marp** (with the plugin) — render saved `--format slides` answers as decks.
- **Dataview** (with the plugin) — build dynamic tables from page frontmatter,
  e.g. list every concept in a section with its `sources` and `updated` date.
  No tool change needed; the pages already carry the frontmatter.
- **Images** — ingested images live in `raw/assets/` and are embedded in their
  source page, so they display inline instead of relying on fragile URLs.

### UC9 — Read in the browser (web UI)
```bash
pip install ".[web]"     # one-time
llmwiki                  # no command → opens http://127.0.0.1:8000
```
Need a different address or no auto-open? Use the explicit form:
`llmwiki serve --port 8080 --host 0.0.0.0 --no-open`.

Renders math via bundled KaTeX, with a section scope tree, clickable links, a
search box, an Ask panel, and a Lint view. Works fully offline; a key is needed
only for Ask and deep Lint. The web UI is a **reader** — it never modifies
`log.md` or your pages.

### UC10 — Track what happened, when (the log)
`wiki/log.md` is an append-only timeline. Each entry is a greppable heading:
```bash
grep '^## \[' wiki/log.md | tail -10      # last 10 operations
grep '^## \[.*ingest' wiki/log.md          # just ingests
```
Entries look like `## [2026-06-16] ingest | Lecture 3` with an optional detail
line. Don't edit it by hand.

### UC11 — Switch providers or tune retrieval
Edit `.llmwiki/config.toml`:
```toml
[settings]
provider = "anthropic"              # or "openai" (default)
default_section = "non-academic"    # used when --section is omitted
search_top_k = 8                    # pages retrieved per query
context_token_budget = 60000        # max context tokens for query/lint
```
Set the matching env key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). Keys never go
in the config. See [README §9](README.md#9-configuration) for model overrides.

### UC12 — Widen scope or add a course
- **Widen a query** to span more of the base: point it at a parent section, or
  drop `--section` to use General. `--section academic` spans all courses.
- **Add a course**: just ingest into it — `--section academic/quantum-mechanics`
  creates the branch on first use.

---

## 5. Command cheat-sheet

| Command | Key? | Use it to |
| ------- | ---- | --------- |
| `llmwiki init [path]` | no | Create a vault. |
| `llmwiki ingest <path\|url> [--section P] [--vision] [--force]` | yes | Compile a source into the wiki. |
| `llmwiki query "<q>" [--section P] [--save] [--format\|-f prose\|table\|slides]` | yes | Answer from the wiki, with citations. |
| `llmwiki search "<kw>" [--section P] [--top-k N]` | no | Fast keyword ranking over concepts. |
| `llmwiki lint [--section P] [--deep]` | `--deep` only | Structural checks; deep adds an LLM review + growth suggestions. |
| `llmwiki` (no command) | for Ask/deep-lint | Launch the browser UI. |

Full flag descriptions live in [README §5](README.md#5-commands).

---

## 6. Best practices

- **Ingest one source at a time and stay involved** — read the summary, check the
  updated pages, then ingest the next. You curate; the LLM files.
- **Let the LLM own `wiki/`.** Don't hand-edit concept/source pages; re-ingest or
  ask instead. Never edit `index.md` or `log.md` (they're regenerated/appended).
- **Save answers worth keeping** with `--save` so explorations compound instead
  of vanishing into chat history.
- **Lint periodically**, especially `--deep` after a batch of ingests, to catch
  contradictions and find the next things to read.
- **Keep raw sources immutable** — they're your audit trail. Edit the source file
  and re-ingest if something changed upstream.

---

## 7. Troubleshooting

Common issues (missing API key, `model_not_found`, `command not found: llmwiki`,
`ModuleNotFoundError`, flaky `pip`) are covered in
[README §11](README.md#11-troubleshooting).

---

## 8. Keeping this manual accurate

This manual is part of the project's documentation and is expected to track the
code. Whenever you (or an assistant) change a command, flag, operation, config
key, page format, or supported source type, update the relevant use case and the
command cheat-sheet above in the **same change**. The README's command reference
and this manual should always agree.
