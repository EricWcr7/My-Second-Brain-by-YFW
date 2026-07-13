# My-Second-Brain-by-YFW

A local-first **LLM Wiki web app**. Drop in your materials — Markdown, PDFs,
slides, Word docs, images, or web URLs — and an LLM compiles them into a
persistent, interlinked, **Obsidian-compatible** Markdown wiki that you browse,
search, and ask questions of, **all in your browser, all on your machine**.

- **Concept-centric** — one page per concept (definition, theorems, notation,
  formulas, proof ideas, examples) plus one page per source.
- **Hierarchical scope** — General → Academic (+ your own top-level branches) →
  courses; every scope runs the same operations over its slice (see
  [Hierarchy & scope](#hierarchy--scope)).
- **Obsidian-native** — `[[wikilinks]]`, YAML frontmatter, `$…$` / `$$…$$` math.
- **Local-first** — no cloud, single-user, your files stay on disk. **Hybrid
  search** (BM25 keyword ⊕ on-disk semantic vectors) + an LLM compiler (OpenAI by
  default; Anthropic/Claude is a one-line config switch).

> 📖 **New here? Start with the [User Manual](USER_MANUAL.md)** — task-based
> walkthroughs of every workflow in the app (ingesting each source type, asking,
> searching, linting, managing courses, Obsidian).


---

## Origin and contributions

This project implements [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): immutable raw sources, an LLM-maintained Markdown wiki, a schema/instruction layer, and ingest/query/lint workflows. I did not originate that overall pattern.

My contributions are the product and implementation design around that foundation:

- hierarchical branches and prefix-scoped knowledge access;
- per-branch purpose, schema, and system-prompt inheritance and overrides;
- the browser UI/UX and workflows for browsing, ingesting, asking, searching, linting, customizing branches, and solving course problems; and
- implementation and evaluation of the resulting application, including provenance checks, hybrid retrieval, provider support, and automated tests.

I designed these extensions and directed the implementation with Claude Code.

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
  run. The stored key is authoritative — it overrides any `OPENAI_API_KEY` /
  `ANTHROPIC_API_KEY` already exported in your shell, so a stale export can't
  shadow it. (To rely on the shell env instead, don't store a key.)
  `llmwiki set-key --show` lists stored keys (masked). Get or
  rotate keys at platform.openai.com → API keys, or console.anthropic.com →
  Settings → API Keys.
- A key is only needed for **Ask**, **Ingest**, **deep Lint**, and **semantic
  search**. Browsing, **keyword** search, and structural lint work offline —
  hybrid search simply falls back to BM25 keyword ranking when no embeddings key
  (or the `[search]` extra) is present.

</details>

---

## Using the app

Everything below happens in the browser. A **persistent top bar** keeps you
oriented on every view: the logo returns to the home page, a live **breadcrumb**
shows where you are, and a **scope chip** shows the section your operations run
over (General sees everything; a course sees only itself) with a one-click **✕ to
reset to General**. Set the scope by picking a node in the sidebar tree or opening
a section's hub — or just open a page: the scope follows the page's section. The
chip and breadcrumb update to match. On narrow screens the sidebar collapses into
a **☰ menu** in the top bar.

- **Browse** — the sidebar shows your section tree and pages; the top-bar
  breadcrumb tracks where you are. Pages render with proper math (KaTeX) and
  clickable `[[wikilinks]]`. Every page/section link behaves the same way —
  sidebar, breadcrumb, wikilinks, and Lint references all navigate consistently,
  and a link to a page that isn't in your wiki tells you instead of doing nothing.
  Each page's reading view carries a **🗑** to delete that one page: deleting a
  concept frees its source for re-ingest; deleting a source is a full teardown
  (its ledger record, cached and raw files go too), removes it from the
  provenance of this section's concepts, and deletes any concept left with no
  sources.
- **Overview** — every section hub (General, each branch, each course) has a
  **Browse overview** that opens an LLM-written orientation to *that* section:
  what it covers and how its ideas connect, with `[[wikilinks]]` into the pages.
  Overviews stay current automatically — each ingest refreshes the section you
  added to **and its parents up to General** — and a **Regenerate overview** button
  rewrites one on demand.
- **Ingest** — the Ingest panel (sidebar, the General card, and each section hub)
  takes one or more **uploaded files** (Markdown/text, PDF, Word, PowerPoint,
  images) **or a URL**, and compiles them into the wiki. A **Destination** picker
  on the form shows exactly which section the new pages will be filed under —
  pre-set to the section you're in (a section hub, or the section of the page
  you're reading) and changeable before you submit. An optional **guidance box**
  lets you steer how a source is compiled (e.g. "focus on the proofs") without
  ever overriding source grounding.
- **Ask** — ask a question answered only from the wiki, with citations back to the
  pages used. You can attach files as **one-off context** for a single answer;
  attachments are never written to the wiki. If an answer cites a page that isn't in
  your wiki, the app flags it so you can distrust that claim (provenance you can see).
- **Solver** — a **Problem Set Solver**: a ChatGPT-style multi-turn chat scoped to
  one configured course section (`solver_section`, e.g. `academic/example-course`).
  Each question runs fresh retrieval over that course's pages and answers with
  **full worked solutions** (rendered math, `[[slug]]` citations, the same
  ungrounded-citation flags as Ask) at **maximum reasoning effort**. Attach
  problem-set **PDFs/images per message** — they're sent natively to the model
  and **never ingested** into the wiki. Sessions persist on disk, are listed in
  a sidebar (resume/delete), and every turn sees the whole conversation. The
  Solver nav entry appears only when `solver_section` is set.
- **Search** — **hybrid** ranking over concept pages: BM25 keyword fused with
  semantic vector search (Reciprocal Rank Fusion), so a query finds the right page
  even with no shared words. Falls back to instant keyword-only ranking offline.
- **Lint** — structural checks, plus an optional **deep** LLM review that flags
  contradictions and suggests what to read next.
- **Branches, courses & sections** — from the homepage, **+ New branch** adds a
  top-level branch (a sibling of Academic); from a section hub, **+ New course** /
  **+ New section** scaffolds a child, and **🗑** deletes one — a full wipe of its
  pages *and* the sources filed under it (ledger, cached/raw files, customizations),
  so nothing orphaned accumulates; the same source can always be re-ingested
  afterward (ingest skips only while a source's pages still exist). The seeded `academic`
  branch is protected. Names keep their exact casing and non-Latin characters
  (`example-course`, `线性代数`).
- **Customize** — each section hub has a **Customize** view to tailor the LLM
  instruction set *for that branch*: the prompt for each operation (ingest
  analysis, ingest generation, answer, solver, lint) plus the branch's **purpose** and
  **schema**. A branch either carries its own override or inherits the **general
  default**; one Save can fan out to several branches still on the default. This is
  how a proof-heavy course (e.g. `example-course`) keeps math/theorem/proof rules while
  everything else stays general.

Prefer Obsidian for reading? Open the `wiki/` folder as a vault — you get the graph
view, backlinks, Marp decks, and Dataview tables for free, since the pages already
carry the right frontmatter. Full workflows are in the **[User Manual](USER_MANUAL.md)**.

---

## Hierarchy & scope

Knowledge lives in a tree of **sections** — a `/`-joined path like
`academic/multivariable-calculus`; the empty path is the **General** root.

```
General (root)            → can access the ENTIRE knowledge base
├── Academic              → all courses' knowledge
│   └── <course>          → only that course (default)
└── <your branch>         → a top-level branch you add (e.g. Personal, Work)
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
   pages and the source page. Optional user **guidance** steers both passes and is
   journaled to `log.md`. Re-ingesting identical content into the same section is
   skipped only while all of its pages still exist in the wiki — deleting pages,
   providing guidance, or `--force` always re-ingests. The check is content-based,
   so a re-downloaded copy under a new filename (`notes (1).pdf`) is recognized as
   the same source. A source larger than `ingest_segment_max_tokens` is
   compiled in segments that each merge into the same pages, so very large files
   (e.g. a 1000-page PDF) stay within the model's context window — still one
   source, one provenance record. Segmented compilation is **atomic**: pages are
   written only after every segment succeeds, so a failure partway leaves the wiki
   unchanged and safe to retry (ingest runs under the longer
   `ingest_request_timeout`). `index.md` is regenerated and `log.md` appended,
   deterministically.
2. **Ask** — hybrid (keyword ⊕ vector) search retrieves candidate pages; an
   optional LLM **rerank** pass (`rerank`, off by default) reorders the top
   `rerank_candidates` by relevance; a token-budgeted context is assembled, and the
   model answers with citations to wiki pages (which point back to sources, which
   point back to your raw files).
3. **Lint** — structural checks plus an optional model review.

Ingesting a source also **embeds** the new pages into the on-disk vector index;
`llmwiki reindex` rebuilds it from scratch (e.g. after installing the `[search]`
extra or changing `embed_model`).

Each operation's system prompt is the packaged **general default** plus the
wiki's `purpose.md` / `schema.md` — unless the section being operated on has its
own override (see **Customize** above), which replaces the default for that branch
only.

Every concept page carries `sources:` provenance, so claims trace back to a source
page and ultimately to the local raw file. Unlike classic RAG, the knowledge is
**compiled once and kept current**, so answers compound over time.

## Vault layout

| Path | Role |
| ---- | ---- |
| `raw/` | Source of truth — your ingested files (`sources/`, `assets/`). Immutable. |
| `wiki/` | Generated layer: `concepts/<section>/`, `sources/<section>/`, `queries/`, `overviews/<section>.md` (per-section overviews), `index.md`, `log.md`, `overview.md` (General overview), `purpose.md`, `schema.md`. |
| `.llmwiki/` | Tool state: `config.toml`, `state.json` (ingest ledger — bookkeeping; the wiki pages, not the ledger, decide re-ingest skips), normalized cache + `lancedb/` vector index (gitignored), `solver/` — Problem Set Solver sessions (chat transcripts + attached files; app data, never wiki pages), and `sections/<section>/<component>.md` — per-branch LLM instruction overrides. |
| `llmwiki/` | The Python package (the app itself). |

## Supported sources

Markdown / plain text, text PDFs (PyMuPDF, with a vision fallback for scanned/math
PDFs), Word `.docx`, PowerPoint `.pptx`, images (vision), and web URLs.

## Configuration

`.llmwiki/config.toml` (created on init):

```toml
[settings]
provider = "openai"                 # "openai" (default) or "anthropic"
# compile_model = "gpt-5.6-sol"     # ingest + answer model (optional; GPT-5.5+)
# cheap_model = "gpt-5.6-sol"       # reserved for cheap ops (optional)
default_section = ""                # default scope when none is given ("" = General root)
search_top_k = 8                    # pages retrieved per question
context_token_budget = 60000        # max context tokens for Ask/Lint
hybrid_search = true                # fuse keyword + vector search (off = BM25 only)
embed_model = "text-embedding-3-small"  # embedding model used for every section
# embed_base_url = "http://localhost:11434/v1"  # OpenAI-compatible endpoint (e.g. Ollama)
# embed_api_key_env = "OPENAI_API_KEY"          # env var the embeddings key is read from
vector_top_n = 40                   # chunk candidates pulled before fusion
rrf_k = 60                          # Reciprocal Rank Fusion constant
rerank = false                      # opt-in: LLM reranks retrieved pages before answering
rerank_candidates = 20              # candidates pulled before reranking down to search_top_k
chunk_max_chars = 1500              # split a page section longer than this
ingest_segment_max_tokens = 60000   # compile a larger source in segments
pdf_vision_min_chars_per_page = 100 # below this, a PDF is transcribed via vision
request_timeout = 300.0             # seconds before a provider call times out
ingest_request_timeout = 3600.0     # longer ceiling for ingest only (big/multi-pass sources)
max_retries = 2                     # retries for transient provider failures
# solver_section = "academic/example-course"  # enable the Problem Set Solver, scoped to this section
solver_reasoning_effort = "xhigh"   # solver-turn reasoning effort (OpenAI; Anthropic ignores)
solver_request_timeout = 600.0      # per-turn ceiling for solver calls (max effort runs long)
```

Semantic search needs the **`[search]`** extra (`pip install ".[web,search]"`,
which adds LanceDB) and an embeddings key. Embeddings are **decoupled from the chat
provider** — they always go through an OpenAI-compatible `/v1/embeddings` endpoint,
so semantic search works even on the Anthropic chat backend, or against a local
endpoint via `embed_base_url`. After changing `embed_model`, run `llmwiki reindex`
to rebuild the vector index.

Both OpenAI and Anthropic support every operation. Leave the models unset to use
the defaults — OpenAI `gpt-5.6-sol` (a reasoning model run at `high` reasoning effort);
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
- **`model_not_found` / no access to `gpt-5.6-sol`** — point `compile_model` (and
  `cheap_model`) in `.llmwiki/config.toml` at a GPT-5.5+ reasoning model you do have
  (e.g. `gpt-5.5`). Keep it 5.5+ — the `high` reasoning effort needs it.
- **`command not found: llmwiki`** — your virtualenv isn't active; run
  `source .venv/bin/activate`.
- **`ModuleNotFoundError: No module named 'llmwiki'`** — you installed editable
  (`-e`); reinstall as a regular package: `pip install --force-reinstall --no-deps .`
  (or run with `PYTHONPATH="$PWD" python -m llmwiki.cli`).
- **`pip` downloads fail ("not enough bytes received")** — add
  `--retries 20 --resume-retries 20 --timeout 60`.
