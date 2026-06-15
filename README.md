# My-Second-Brain-by-YFW

A local-first **LLM Wiki / knowledge base**. `llmwiki` compiles local materials
(Markdown, PDFs, slides, Word docs, images, web URLs) into a persistent,
**Obsidian-compatible** Markdown wiki organized as a **section hierarchy**. Raw
sources stay local and remain the source of truth; the generated `wiki/` pages are
an editable, citation-aware layer over everything you know — academic or not.

- **Concept-centric** — one page per concept (definition, theorems, assumptions,
  notation, formulas, proof ideas, examples) plus one page per source.
- **Hierarchical scope** — General → Academic / Non-academic → courses. Every
  level runs the *same* operations; the only difference is how much of the base
  it can access (see [Hierarchy & scope](#hierarchy--scope)).
- **Obsidian-native** — `[[wikilinks]]`, YAML frontmatter, `$…$`/`$$…$$` math.
- **No vectors / no embeddings / no cloud / single-user** — keyword search + an
  LLM compiler (OpenAI by default; Anthropic/Claude is a config switch away).

> 📖 **New here? Start with the [User Manual](USER_MANUAL.md)** — task-based
> walkthroughs of every use case (ingesting each source type, querying, answer
> formats, Obsidian, the web UI, and more). This README covers install,
> configuration, and the command reference.

---

## Hierarchy & scope

Knowledge lives in a tree of **sections** — a `/`-joined path like
`academic/multivariable-calculus`; the empty path is the **General** root.

```
General (root)            → can access the ENTIRE knowledge base
├── Non-academic (flat)   → only non-academic knowledge
└── Academic              → all courses' knowledge
    └── <course>          → only that course (default)
```

Every operation takes an optional `--section` and obeys a **prefix rule**: a scope
sees a page iff the scope is a prefix of the page's section. To widen a course
query, point it at a parent (`--section academic`, or omit `--section` for
General). The [User Manual](USER_MANUAL.md#2-core-concepts-you-need-before-starting)
has the full explanation, examples, and how to add a course.

---

## 1. Requirements

- Python **3.11+**
- An **API key for your chosen provider** — `OPENAI_API_KEY` (default) or
  `ANTHROPIC_API_KEY`. Only needed for `ingest`, `query`, and `lint --deep`;
  `init`, `search`, and plain `lint` work offline.

## 2. Install

```bash
# from the repo root
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install ".[dev]"                # runtime deps + pytest; drop [dev] to skip tests
```

> **Use the regular install above, not `pip install -e .` (editable).** Editable
> installs rely on a `.pth` file that some Python builds — including the
> python.org macOS framework build — don't load at startup, which produces
> `ModuleNotFoundError: No module named 'llmwiki'`. A regular install copies the
> package into the venv so it always imports. If you change the tool's own source
> later, re-apply it with `pip install --force-reinstall --no-deps .`.

Hardened variant (forces prebuilt wheels for dependencies, so none run build
scripts during install):

```bash
pip install --only-binary :all: ".[dev]"
```

## 3. Set your API key

`llmwiki` reads the key from an environment variable at runtime — **`OPENAI_API_KEY`**
for the default OpenAI backend, or **`ANTHROPIC_API_KEY`** if you set
`provider = "anthropic"`. Keys are **never** written to the vault or
`.llmwiki/config.toml`.

```bash
export OPENAI_API_KEY=sk-...             # default provider; this terminal only
# or, if provider = "anthropic":
export ANTHROPIC_API_KEY=""
```

> `export` lasts only for the current terminal. Open a new window and you must
> set it again — or run your `llmwiki` commands in the same terminal.

To persist it across terminals, add it to your shell profile:

```bash
echo 'export OPENAI_API_KEY=sk-...' >> ~/.zshrc   # bash: ~/.bashrc
source ~/.zshrc
```

Verify it's set (without exposing the whole key):

```bash
echo ${OPENAI_API_KEY:0:7}         # prints just the first 7 chars
```

Get or rotate keys at **platform.openai.com → API keys** (OpenAI) or
**console.anthropic.com → Settings → API Keys** (Anthropic). A key's full value
is shown **only once at creation** — if you lost it, create a new one.

## 4. Quick start

```bash
llmwiki init                                          # scaffold raw/, wiki/, .llmwiki/
llmwiki ingest examples/sample_calculus.md --section academic/multivariable-calculus
llmwiki ingest https://en.wikipedia.org/wiki/Gradient --section academic/multivariable-calculus
llmwiki query "state the multivariable chain rule and the proof idea" --section academic
llmwiki search "chain rule"                           # keyword search, no LLM, no key
llmwiki lint                                          # structural checks (offline)
llmwiki lint --deep                                   # + LLM contradiction/gap review
```

Then open the `wiki/` folder in **Obsidian** to read, search, graph, and edit —
or just run `llmwiki` (no command) for a browser view that renders the math (see §5).

For end-to-end workflows (building a course, ingesting each source type, saving
answers, Obsidian/Marp/Dataview), see the **[User Manual](USER_MANUAL.md)**.

---

## 5. Commands

### `init [path]`
Create a vault in the given directory (default: current directory). Scaffolds
`raw/`, `wiki/` (with seed `purpose.md` / `schema.md`), and `.llmwiki/`.

### `ingest <path|url> [--section PATH] [--vision] [--force]`
Compile one source into the wiki.
- `--section` — which section the source belongs to, e.g.
  `academic/multivariable-calculus` or `non-academic` (default: `default_section`
  in config). Sets a frontmatter field **and** a nested subfolder.
- `--vision` — force vision transcription for a PDF (use for scanned or
  math-heavy PDFs where text extraction is poor).
- `--force` — re-ingest even if the file is unchanged (normally an unchanged
  source is skipped via its SHA256 checksum).

External files are **copied into `raw/sources/`** so the vault stays
self-contained. Re-ingesting an edited source merges the new material into the
existing concept pages.

### `query "<question>" [--section PATH] [--save] [--format prose|table|slides]`
Answer a question using only the wiki, with citations back to the pages used.
- `--section` — restrict retrieval to a section and its subtree (omit for the
  whole knowledge base; see [Hierarchy & scope](#hierarchy--scope)).
- `--save` — also write the answer to `wiki/queries/`.
- `--format` — `prose` (default), a Markdown `table` comparison, or a Marp
  `slides` deck. All text-only; saved decks get a `marp: true` frontmatter flag
  so Obsidian's Marp plugin renders them.

### `search "<keywords>" [--section PATH] [--top-k N]`
Fast keyword (BM25-lite) ranking over concept pages. No LLM, no API key.

### `lint [--section PATH] [--deep]`
Quality checks.
- Always: dangling `[[wikilinks]]`, missing/unresolved `sources:` provenance,
  orphan pages, malformed frontmatter (offline).
- `--deep` — additionally ask the model to flag contradictions, missing concept
  pages, and stale/unclear claims, plus growth suggestions: missing
  cross-references, new questions to investigate, sources to seek, and data gaps
  a web search could fill (uses the API).

### Web UI
Read the wiki in a browser with **properly rendered math** (`$…$` / `$$…$$` via
KaTeX), clickable `[[wikilinks]]`, keyword search, an Ask panel, and a Lint view.
Just run `llmwiki` with no command from the vault root — it starts the UI and
opens `http://127.0.0.1:8000` in your browser.

```bash
pip install ".[web]"      # one-time: adds fastapi + uvicorn
llmwiki                   # opens the web UI in your browser
```

The rendering libraries (KaTeX, markdown-it) are bundled into the committed
build, so the UI works fully offline and **no Node is needed to run it**. A key
is only needed for the Ask panel and Lint's deep review; browse/search/structural
-lint work without one.

### Developing the web UI

The frontend is a Vite + TypeScript app in `llmwiki/web/frontend/`; its build
output is committed to `llmwiki/web/static/` (which the FastAPI app hosts). Node
is required only for development, not for running.

```bash
make web-install   # one-time: npm install (needs Node 18+)
make dev           # FastAPI :8000 + Vite :5173 (HMR) — open http://127.0.0.1:5173
make web-build     # rebuild llmwiki/web/static before committing UI changes
```

`make dev` proxies `/api` to the backend, so editing `src/*.ts` or
`src/styles.css` reloads instantly — no reinstall, no hard refresh.

---

## 6. How it works

Three layers, three operations (raw sources → LLM-compiled wiki → schema):

1. **Ingest** — a loader normalizes the source to Markdown (vision is used only
   for images and scanned/math PDFs), it's checksummed and cached, then an
   *analysis* pass decides which concepts it teaches and a *generation* pass
   writes/merges the concept pages and the source page. `index.md` is regenerated
   and `log.md` appended — all deterministically.
2. **Query** — keyword search retrieves candidate pages, a token-budgeted context
   is assembled, and the model answers with citations to wiki pages (which point
   back to sources, which point back to raw files).
3. **Lint** — structural checks plus an optional model review.

Every concept page carries `sources:` provenance, so claims trace back to a
source page and ultimately to the local raw file.

## 7. Vault layout

| Path          | Role                                                              |
| ------------- | ---------------------------------------------------------------- |
| `raw/`        | Source of truth — your dropped files (`sources/`, `assets/`).     |
| `wiki/`       | Generated study layer: `concepts/<section>/`, `sources/<section>/`, `index.md`, `log.md`, `overview.md`, `purpose.md`, `schema.md`. |
| `.llmwiki/`   | Tool state: `config.toml`, `state.json`, normalized cache (gitignored). |
| `llmwiki/`    | The Python package (the tool itself).                            |

## 8. Supported sources

Markdown / plain text, text-based PDFs (PyMuPDF, with a vision fallback for
scanned/math PDFs), Word `.docx`, PowerPoint `.pptx`, images (vision), and web
URLs.

## 9. Configuration

`.llmwiki/config.toml` (created by `init`):

```toml
[settings]
provider = "openai"                 # "openai" (default) or "anthropic"
# compile_model = "gpt-5.5"         # ingest + answer model (optional; gpt-5.5+)
# cheap_model = "gpt-5.5"           # reserved for cheap ops (optional override)
default_section = "non-academic"    # section used when --section is omitted
search_top_k = 8                    # pages retrieved per query
context_token_budget = 60000        # max context tokens for query/lint
pdf_vision_min_chars_per_page = 100 # below this, a PDF is transcribed via vision
```

`provider` selects the backend; both OpenAI and Anthropic support every
operation (ingest, query, lint, and PDF/image vision). Leave `compile_model` /
`cheap_model` unset to use the provider's defaults — OpenAI: `gpt-5.5` (a
**reasoning model run at `xhigh` reasoning effort**); Anthropic: `claude-opus-4-8`
/ `claude-haiku-4-5`. If you override the OpenAI model, keep it a GPT-5.5+
reasoning model — `xhigh` effort is only valid on those.

API keys are read from the environment — never put them here.

## 10. Tests

```bash
pytest        # unit tests; the LLM is mocked, so no API key is required
```

## 11. Troubleshooting

- **API key not set / auth error** — set `OPENAI_API_KEY` (default) or
  `ANTHROPIC_API_KEY` (if `provider = "anthropic"`); see §3. Remember `export`
  is per-terminal.
- **`model_not_found` / no access to `gpt-5.5`** — your OpenAI account may not
  have that model yet. Point `compile_model` (and `cheap_model`) at a GPT-5.5+
  reasoning model you do have in `.llmwiki/config.toml`, e.g. `compile_model =
  "gpt-5.6"`. Keep it 5.5+ — the `xhigh` reasoning effort llmwiki sends is only
  valid on those models.
- **`zsh: command not found: llmwiki`** — your virtualenv isn't active. From the
  repo root run `source .venv/bin/activate`, then retry.
- **`ModuleNotFoundError: No module named 'llmwiki'`** — you installed in editable
  mode (`-e`) and this Python build didn't load the editable `.pth`. Reinstall as
  a regular package:
  ```bash
  pip install --force-reinstall --no-deps .
  ```
  (One-off alternative without reinstalling: run from the repo root with
  `PYTHONPATH="$PWD" python -m llmwiki.cli <args>`.)
- **`pip` downloads fail with "not enough bytes received"** (flaky network) —
  add resume + retries:
  ```bash
  pip install --retries 20 --resume-retries 20 --timeout 60 -e ".[dev]"
  ```
