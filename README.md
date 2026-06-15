# My-Second-Brain-by-YFW

A local-first **academic LLM Wiki**. `llmwiki` compiles local course materials
(Markdown, PDFs, slides, Word docs, images, web URLs) into a persistent,
**Obsidian-compatible** Markdown study wiki. Raw sources stay local and remain
the source of truth; the generated `wiki/` pages are an editable, citation-aware
study layer for proof-heavy courses.

- **Concept-centric** — one page per concept (definition, theorems, assumptions,
  notation, formulas, proof ideas, examples) plus one page per source.
- **Obsidian-native** — `[[wikilinks]]`, YAML frontmatter, `$…$`/`$$…$$` math.
- **No vectors / no embeddings / no cloud / single-user** — keyword search + an
  LLM compiler (Claude by default).

---

## 1. Requirements

- Python **3.11+**
- An **Anthropic API key** (only needed for `ingest`, `query`, and `lint --deep`;
  `init`, `search`, and plain `lint` work offline)

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

`llmwiki` reads the key from the **`ANTHROPIC_API_KEY` environment variable** at
runtime. It is **never** written to the vault or `.llmwiki/config.toml`.

```bash
export ANTHROPIC_API_KEY=""
```

> `export` lasts only for the current terminal. Open a new window and you must
> set it again — or run your `llmwiki` commands in the same terminal.

To persist it across terminals, add it to your shell profile:

```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc   # bash: ~/.bashrc
source ~/.zshrc
```

Verify it's set (without exposing the whole key):

```bash
echo ${ANTHROPIC_API_KEY:0:7}      # prints just the first 7 chars
```

Get or rotate a key at **console.anthropic.com → Settings → API Keys**. A key's
full value is shown **only once at creation** — if you lost it, create a new one.

## 4. Quick start

```bash
llmwiki init                                          # scaffold raw/, wiki/, .llmwiki/
llmwiki ingest examples/sample_calculus.md --course "Multivariable Calculus"
llmwiki ingest https://en.wikipedia.org/wiki/Gradient --course "Multivariable Calculus"
llmwiki query "state the multivariable chain rule and the proof idea"
llmwiki search "chain rule"                           # keyword search, no LLM, no key
llmwiki lint                                          # structural checks (offline)
llmwiki lint --deep                                   # + LLM contradiction/gap review
```

Then open the `wiki/` folder in **Obsidian** to read, search, graph, and edit.

---

## 5. Commands

### `init [path]`
Create a vault in the given directory (default: current directory). Scaffolds
`raw/`, `wiki/` (with seed `purpose.md` / `schema.md`), and `.llmwiki/`.

### `ingest <path|url> [--course NAME] [--vision] [--force]`
Compile one source into the wiki.
- `--course` — which course the source belongs to (default: `default_course` in
  config). Sets a frontmatter field **and** a per-course subfolder.
- `--vision` — force vision transcription for a PDF (use for scanned or
  math-heavy PDFs where text extraction is poor).
- `--force` — re-ingest even if the file is unchanged (normally an unchanged
  source is skipped via its SHA256 checksum).

External files are **copied into `raw/sources/`** so the vault stays
self-contained. Re-ingesting an edited source merges the new material into the
existing concept pages.

### `query "<question>" [--course NAME] [--save]`
Answer a question using only the wiki, with citations back to the pages used.
- `--course` — restrict retrieval to one course.
- `--save` — also write the answer to `wiki/queries/`.

### `search "<keywords>" [--course NAME] [--top-k N]`
Fast keyword (BM25-lite) ranking over concept pages. No LLM, no API key.

### `lint [--course NAME] [--deep]`
Quality checks.
- Always: dangling `[[wikilinks]]`, missing/unresolved `sources:` provenance,
  orphan pages, malformed frontmatter (offline).
- `--deep` — additionally ask the model to flag contradictions, missing concept
  pages, and stale/unclear claims (uses the API).

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
| `wiki/`       | Generated study layer: `concepts/<course>/`, `sources/<course>/`, `index.md`, `log.md`, `overview.md`, `purpose.md`, `schema.md`. |
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
compile_model = "claude-opus-4-8"   # ingest + answer model
cheap_model = "claude-haiku-4-5"    # reserved for cheap ops
default_course = "General"          # used when --course is omitted
search_top_k = 8                    # pages retrieved per query
context_token_budget = 60000        # max context tokens for query/lint
pdf_vision_min_chars_per_page = 100 # below this, a PDF is transcribed via vision
```

API keys are read from the environment — never put them here.

## 10. Tests

```bash
pytest        # unit tests; the LLM is mocked, so no API key is required
```

## 11. Troubleshooting

- **`ANTHROPIC_API_KEY` not set / auth error** — see §3. Remember `export` is
  per-terminal.
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

## 12. LLM API Key Configuration

### Anthropic
```bash
export ANTHROPIC_API_KEY=""
```

### OpenAI

