# My Second Brain

**English** · [简体中文 →](README.zh-CN.md)

My Second Brain is a local-first knowledge app that turns PDFs, notes, Word and
PowerPoint files, images, and web pages into a connected, searchable,
Obsidian-compatible Markdown wiki.

Instead of leaving useful context inside disposable model conversations, the app
builds a durable knowledge layer on disk: raw source files, linked concept pages,
source provenance, scoped overviews, and an operation log. You can compile new
material, browse and search it, ask questions grounded in the wiki, review its
structure, and optionally solve course problems in a persistent chat.

> **Local-first is not fully offline.** Your vault and generated pages remain on
> your machine. AI-powered operations send the source or context needed for that
> operation to the OpenAI or Anthropic provider you configure.

For complete usage, configuration, deletion behavior, privacy guidance, and
troubleshooting, open the [User Manual](USER_MANUAL.md).

## What the app provides

- **Durable Markdown knowledge** — YAML frontmatter, `[[wikilinks]]`, and LaTeX
  math stay readable outside the app.
- **Source-aware compilation** — each import creates or updates concept pages and
  keeps provenance back to a source page and raw material.
- **Hierarchical scopes** — work across the entire vault or narrow Search, Ask,
  Review, and Add source to a branch or course.
- **Grounded answers** — answers cite wiki pages; citations to nonexistent pages
  are shown as warnings instead of being silently accepted.
- **Hybrid retrieval** — local BM25 keyword search works by default; optional
  LanceDB vectors add semantic search.
- **Inspectable instructions** — each scope can override the prompts, purpose,
  and schema used for compilation, answering, review, and Solver.
- **Web and CLI workflows** — use the browser for daily work and `llmwiki` for
  setup, scripting, saved answers, and maintenance.

## Quick start

### Requirements

- Python 3.11 or newer
- Git
- An OpenAI or Anthropic API key for AI-powered features

Node.js is not required to run the app. It is needed only when changing the
frontend.

### Launch the included sample vault

This repository already contains a populated example-course sample vault. Clone it,
install the package, and launch from the repository root:

```bash
git clone https://github.com/EricWcr7/My-Second-Brain-by-YFW.git
cd My-Second-Brain-by-YFW
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[web]"
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

On Windows PowerShell, create and activate the environment with a Python 3.11+
installation:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install ".[web]"
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

Replace `YOUR_OPENAI_API_KEY` with the real key; do not commit it. The key is
stored outside the vault at `$XDG_CONFIG_HOME/llmwiki/.env` when
`XDG_CONFIG_HOME` is set, or `~/.config/llmwiki/.env` otherwise. Passing a key as
a command-line argument may leave it in shell history; use your shell's protected
secret-input or environment-variable workflow when that matters. To use
Anthropic for the main app instead, see
[Provider setup](USER_MANUAL.md#provider-keys-and-models).

The server opens `http://127.0.0.1:8000`. Select **Enter workspace** on the
Welcome screen. Stop the server with `Ctrl+C`.

You may omit the key command if you only want to browse the included wiki, run
keyword Search, or use structural Review.

### Create a clean personal vault

After installing `llmwiki` from the cloned repository, initialize a different
directory:

```bash
llmwiki init ~/my-second-brain
cd ~/my-second-brain
llmwiki
```

`llmwiki init` is idempotent: it creates missing vault files without overwriting
existing content. A clean vault includes the protected `Academic` scope, but it
does not include the sample course or enable Solver.

### Your first five minutes

1. Select **Enter workspace**.
2. Keep the `General` scope for the whole vault, or open **Scope → Manage scopes**
   to create or select a narrower scope.
3. Select **Add source**, choose one or more files or a URL, confirm the
   destination, and compile.
4. Use the Workspace field or **Search** (`Cmd/Ctrl+K`) to open the generated
   concepts and source pages.
5. Open **Ask** for a synthesized answer or **Review** to check provenance and
   links.

## Optional semantic search

Install the search extra from the cloned repository:

```bash
python -m pip install ".[web,search]"
```

Then rebuild vectors from inside the vault:

```bash
llmwiki reindex
```

Semantic search also needs an embeddings key or an OpenAI-compatible local
endpoint. Without it—or without the search extra—the app falls back to BM25
keyword search.

## Scope model

A scope sees pages in its own section and every descendant section. `General`
therefore sees the entire vault; a course sees only that course.

```text
General
├── Academic
│   └── example-course
├── Research
└── Personal
```

Scopes organize retrieval; they are not user accounts or security boundaries.
The app is designed for one user and has no authentication layer.

## Vault layout

| Path | Purpose |
| --- | --- |
| `raw/` | Local copies of ingested files and image assets |
| `wiki/` | Generated concept pages, source pages, overviews, index, log, purpose, and schema |
| `.llmwiki/` | Vault configuration, ingest state, normalized cache, optional vectors, prompt overrides, and Solver sessions |

The wiki remains plain Markdown, so it can be inspected with Git, a text editor,
or Obsidian. The [User Manual](USER_MANUAL.md#storage-backup-and-obsidian)
explains which directory to open and what to back up.

## Command-line entry points

```text
llmwiki init       Create or complete a vault
llmwiki ingest     Compile one file or URL
llmwiki query      Ask from the terminal; optionally save the answer
llmwiki search     Search concept pages
llmwiki lint       Run structural or deep review
llmwiki overview   Regenerate an overview
llmwiki reindex    Rebuild semantic vectors
llmwiki set-key    Store or inspect provider keys
llmwiki             Launch the web app
```

See the [CLI reference](USER_MANUAL.md#command-line-reference) for options and
examples.

## Development

Install test dependencies and run the Python suite:

```bash
python -m pip install ".[dev]"
make test
make eval
```

For frontend development:

```bash
make web-install
make dev
```

`make dev` runs FastAPI on port 8000 and Vite on port 5173. After changing
frontend source, run `make web-build` to rebuild the committed production assets
under `llmwiki/web/static/`.

## Origin and license

The project implements and extends
[Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
immutable source material, an LLM-maintained Markdown wiki, an instruction/schema
layer, and ingest/query/review workflows. This implementation adds hierarchical
scopes, branch-specific instructions, hybrid retrieval, the browser experience,
provider support, persistent Solver sessions, and automated grounding checks.

Released under the [MIT License](LICENSE).
