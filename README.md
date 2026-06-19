# My-Second-Brain-by-YFW

A local-first **LLM Wiki web app**. Drop in your materials — Markdown, PDFs,
slides, Word docs, images, or web URLs — and an LLM compiles them into a
persistent, interlinked, **Obsidian-compatible** Markdown wiki that you browse,
search, and ask questions of, **all in your browser, all on your machine**.

- **Concept-centric** — one page per concept (definition, theorems, notation,
  formulas, proof ideas, examples) plus one page per source.
- **Hierarchical scope** — General → Academic / Non-academic → courses; every
  scope runs the same operations over its slice (see [Hierarchy & scope](#hierarchy--scope)).
- **Obsidian-native** — `[[wikilinks]]`, YAML frontmatter, `$…$` / `$$…$$` math.
- **Local-first** — no cloud, single-user, your files stay on disk. Keyword search
  + an LLM compiler (OpenAI by default; Anthropic/Claude is a one-line config switch).

> 📖 **New here? Start with the [User Manual](USER_MANUAL.md)** — task-based
> walkthroughs of every workflow in the app (ingesting each source type, asking,
> searching, linting, managing courses, Obsidian).

---

## Run the app

You need **Python 3.11+** and an **API key** for your provider (`OPENAI_API_KEY`
by default, or `ANTHROPIC_API_KEY`). From the repo root:

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install ".[web]"                # installs the app (FastAPI + the runtime)
llmwiki set-key openai sk-...        # store your key once (~/.config/llmwiki/.env, mode 600)
llmwiki init                         # create a vault here (raw/, wiki/, .llmwiki/)
llmwiki                              # launch → opens http://127.0.0.1:8000
```

That's the whole setup — after this, **everything happens in the browser.** To
bind a different address or skip auto-opening: `llmwiki serve --port 8080 --host
0.0.0.0 --no-open`.

<details>
<summary>Install notes (editable installs, offline wheels, key persistence)</summary>

- **Don't use `pip install -e .` (editable).** Some Python builds — including the
  python.org macOS framework build — don't load the editable `.pth`, giving
  `ModuleNotFoundError: No module named 'llmwiki'`. A regular install copies the
  package in so it always imports. After changing the tool's own source, re-apply
  with `pip install --force-reinstall --no-deps .`.
- **Hardened install** (prebuilt wheels only, no build scripts):
  `pip install --only-binary :all: ".[web]"`.
- **API key:** `set-key` saves it to `~/.config/llmwiki/.env` and loads it on every
  run. A `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` exported in your shell still wins
  over the stored file. `llmwiki set-key --show` lists stored keys (masked). Get or
  rotate keys at platform.openai.com → API keys, or console.anthropic.com →
  Settings → API Keys.
- A key is only needed for **Ask**, **Ingest**, and **deep Lint**. Browsing,
  keyword search, and structural lint work offline.

</details>

---

## Using the app

Everything below happens in the browser, scoped to whatever section you've selected
in the sidebar (General sees everything; a course sees only itself).

- **Browse** — the sidebar shows your section tree; pages render with proper math
  (KaTeX) and clickable `[[wikilinks]]`.
- **Ingest** — the Ingest panel (sidebar, the General card, and each section hub)
  takes one or more **uploaded files** (Markdown/text, PDF, Word, PowerPoint,
  images) **or a URL**, and compiles them into the wiki at your current scope.
- **Ask** — ask a question answered only from the wiki, with citations back to the
  pages used. You can attach files as **one-off context** for a single answer;
  attachments are never written to the wiki.
- **Search** — instant keyword ranking over concept pages (no key needed).
- **Lint** — structural checks, plus an optional **deep** LLM review that flags
  contradictions and suggests what to read next.
- **Courses & sections** — from a section hub, **+ New course** scaffolds a branch
  and **🗑** deletes one (the seeded `academic` / `non-academic` branches are
  protected). Names keep their exact casing and non-Latin characters
  (`example-course`, `线性代数`).

Prefer Obsidian for reading? Open the `wiki/` folder as a vault — you get the graph
view, backlinks, Marp decks, and Dataview tables for free, since the pages already
carry the right frontmatter. Full workflows are in the **[User Manual](USER_MANUAL.md)**.

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

Access follows one **prefix rule**: a scope sees a page iff the scope is a prefix
of the page's section. Pick a scope in the sidebar; to widen, pick a parent
(Academic, or General for everything). Scope *is* access — there's no separate
sharing mechanism.

---

## How it works

Three layers (raw sources → LLM-compiled wiki → schema), three operations:

1. **Ingest** — a loader normalizes the source to Markdown (vision for images and
   scanned/math PDFs), it's checksummed and cached, then an *analysis* pass decides
   which concepts it teaches and a *generation* pass writes/merges the concept
   pages and the source page. `index.md` is regenerated and `log.md` appended,
   deterministically.
2. **Ask** — keyword search retrieves candidate pages, a token-budgeted context is
   assembled, and the model answers with citations to wiki pages (which point back
   to sources, which point back to your raw files).
3. **Lint** — structural checks plus an optional model review.

Every concept page carries `sources:` provenance, so claims trace back to a source
page and ultimately to the local raw file. Unlike classic RAG, the knowledge is
**compiled once and kept current**, so answers compound over time.

## Vault layout

| Path | Role |
| ---- | ---- |
| `raw/` | Source of truth — your ingested files (`sources/`, `assets/`). Immutable. |
| `wiki/` | Generated layer: `concepts/<section>/`, `sources/<section>/`, `queries/`, `index.md`, `log.md`, `overview.md`, `purpose.md`, `schema.md`. |
| `.llmwiki/` | Tool state: `config.toml`, `state.json`, normalized cache (gitignored). |
| `llmwiki/` | The Python package (the app itself). |

## Supported sources

Markdown / plain text, text PDFs (PyMuPDF, with a vision fallback for scanned/math
PDFs), Word `.docx`, PowerPoint `.pptx`, images (vision), and web URLs.

## Configuration

`.llmwiki/config.toml` (created on init):

```toml
[settings]
provider = "openai"                 # "openai" (default) or "anthropic"
# compile_model = "gpt-5.5"         # ingest + answer model (optional; GPT-5.5+)
# cheap_model = "gpt-5.5"           # reserved for cheap ops (optional)
default_section = "non-academic"    # default scope when none is given
search_top_k = 8                    # pages retrieved per question
context_token_budget = 60000        # max context tokens for Ask/Lint
pdf_vision_min_chars_per_page = 100 # below this, a PDF is transcribed via vision
```

Both OpenAI and Anthropic support every operation. Leave the models unset to use
the defaults — OpenAI `gpt-5.5` (a reasoning model run at `high` reasoning effort);
Anthropic `claude-opus-4-8` / `claude-haiku-4-5`. If you override the OpenAI model,
keep it GPT-5.5+ (`high` effort is only valid there). **API keys are read from the
environment — never put them here.**

## Developing the web UI

The frontend is a Vite + TypeScript app in `llmwiki/web/frontend/`; its build output
is committed to `llmwiki/web/static/` (which FastAPI hosts). Node is needed only for
development, not for running.

```bash
pip install ".[dev]"   # adds pytest; run: pytest  (the LLM is mocked, no key needed)
make web-install       # one-time: npm install (Node 18+)
make dev               # FastAPI :8000 + Vite :5173 (HMR) — open http://127.0.0.1:5173
make web-build         # rebuild llmwiki/web/static before committing UI changes
```

## Troubleshooting

- **App says the API key isn't set** — store it with `llmwiki set-key openai sk-...`
  (or `anthropic`), then relaunch. Check with `llmwiki set-key --show`.
- **`model_not_found` / no access to `gpt-5.5`** — point `compile_model` (and
  `cheap_model`) in `.llmwiki/config.toml` at a GPT-5.5+ reasoning model you do have
  (e.g. `gpt-5.6`). Keep it 5.5+ — the `high` reasoning effort needs it.
- **`command not found: llmwiki`** — your virtualenv isn't active; run
  `source .venv/bin/activate`.
- **`ModuleNotFoundError: No module named 'llmwiki'`** — you installed editable
  (`-e`); reinstall as a regular package: `pip install --force-reinstall --no-deps .`
  (or run with `PYTHONPATH="$PWD" python -m llmwiki.cli`).
- **`pip` downloads fail ("not enough bytes received")** — add
  `--retries 20 --resume-retries 20 --timeout 60`.
