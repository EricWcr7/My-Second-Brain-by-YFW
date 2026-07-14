# Second Brain by YFW

**English** · [简体中文 →](README.zh-CN.md)

Second Brain by YFW is a local-first knowledge app that turns documents, images,
and web pages into a connected, searchable, Obsidian-compatible Markdown wiki.
It keeps source provenance, linked concepts, scoped overviews, and an operation
log on disk so the knowledge remains readable outside the app.

> **Local-first does not mean fully offline.** Your vault and generated pages
> remain on your machine. AI-powered operations send the source or context needed
> for that operation to the OpenAI or Anthropic provider you configure.

For browser workflows, configuration, storage, privacy, and troubleshooting, see
the [User Manual](USER_MANUAL.md).

## Highlights

- **Durable Markdown** — YAML frontmatter, `[[wikilinks]]`, and LaTeX math remain
  usable in a text editor or Obsidian.
- **Source-aware ingest** — imports create source records and merge reusable
  concepts while preserving provenance.
- **Scoped knowledge** — Search, Ask, Review, overviews, and ingest can target the
  whole vault or one branch.
- **Grounded answers** — answers cite wiki pages, and citations to missing pages
  are reported.
- **Hybrid retrieval** — BM25 keyword search works locally; optional LanceDB
  vectors add semantic retrieval.
- **Inspectable instructions** — the General baseline and scope-level overrides
  control purpose, schema, ingest, Ask, and deep Review prompts.
- **Browser and CLI workflows** — use the browser day to day and `llmwiki` for
  setup, scripting, saved answers, and maintenance.

## Quick start

### Requirements

- Python 3.11 or newer
- Git
- An OpenAI or Anthropic API key for AI-powered operations

Node.js is needed only for frontend development.

### macOS or Linux

Clone the repository, create an environment, install from the checkout, initialize
an ignored vault, configure a provider key, and launch:

```bash
git clone https://github.com/EricWcr7/second-brain-by-yfw.git
cd second-brain-by-yfw
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

### Windows PowerShell

```powershell
git clone https://github.com/EricWcr7/second-brain-by-yfw.git
cd second-brain-by-yfw
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

Replace the placeholder with a real key and do not commit it. Stored keys live
outside the vault at `${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env`. Because a key
passed on the command line may remain in shell history, use an environment variable
or your shell's protected secret workflow when needed. Anthropic setup is covered
in [Provider keys and models](USER_MANUAL.md#provider-keys-and-models).

The server opens `http://127.0.0.1:8000`. Select **Enter workspace** and stop the
server with `Ctrl+C`. A key is not required to browse existing pages, run BM25
Search, or run structural Review.

### First workflow

1. Open **Scope → Manage scopes** and create or select a destination.
2. Select **Add source**, choose files or enter a URL, and compile them.
3. Use **Workspace** or **Search** (`Cmd/Ctrl+K`) to open generated pages.
4. Use **Ask** for a grounded synthesis.
5. Use **Review** to check provenance and links.

`llmwiki init .` is idempotent: it creates missing vault files without replacing
existing content. To keep the checkout itself free of data, initialize a separate
directory instead:

```bash
mkdir my-vault
cd my-vault
llmwiki init .
llmwiki
```

## Supported sources

The ingest pipeline accepts Markdown, plain text, PDF, DOCX, PPTX, common image
formats, and HTTP(S) web pages. Text is extracted locally first. Images and sparse
or scanned PDFs use the configured provider's vision input. Provider calls may
therefore receive document text or original image/PDF bytes.

## Optional semantic search

Install the search extra from the repository checkout, configure an embeddings
key or OpenAI-compatible endpoint, then build vectors from the vault:

```bash
python -m pip install ".[web,search]"
llmwiki reindex
```

Without the extra, an embeddings key, or a vector index, Search falls back to
local BM25 ranking.

## Scope model

A scope sees its own section and all descendant sections. `General` sees the
whole vault; a child scope sees only its branch.

```text
General
├── Academic
│   └── Example Course
└── Projects
    └── Learning Notes
```

Scopes organize retrieval. They are not accounts, permissions, or security
boundaries; the app is designed for one user and has no authentication layer.

## Vault layout

The public repository contains application code only. Running `llmwiki init .`
creates these ignored runtime directories:

| Path | Purpose |
| --- | --- |
| `raw/` | Local copies of ingested files and image assets |
| `wiki/` | Generated concepts, source pages, overviews, index, log, purpose, and schema |
| `.llmwiki/` | Configuration, ingest state, normalized cache, optional vectors, and prompt overrides |

Back up the whole vault when you need an exact restore. The `wiki/` directory
alone is a portable reading copy.

## Command-line overview

```text
llmwiki init       Create or complete a vault
llmwiki ingest     Compile one file or URL
llmwiki query      Ask from the terminal; optionally save the answer
llmwiki search     Search concept pages
llmwiki lint       Run structural or deep review
llmwiki overview   Regenerate an overview
llmwiki reindex    Rebuild semantic vectors
llmwiki set-key    Store or inspect provider keys
llmwiki            Launch the web app
```

See the [CLI reference](USER_MANUAL.md#command-line-reference) for options and
examples.

## Development

Install development dependencies and run the Python tests and grounding
evaluations:

```bash
python -m pip install ".[dev]"
make test
make eval
```

For frontend work:

```bash
make web-install
make dev
```

`make dev` runs FastAPI on port 8000 and Vite on port 5173. After changing
frontend source, run `make web-build` and commit the refreshed production bundle
under `llmwiki/web/static/`.

## Origin, artwork, and licenses

This project implements and extends
[Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
immutable source material, an LLM-maintained Markdown wiki, an instruction/schema
layer, and ingest/query/review workflows.

The bundled `brain-network.png` illustration was created by EricWcr7 for this
project and is distributed under the repository's [MIT License](LICENSE).
Third-party fonts and libraries retain their own licenses; see
[Third-Party Notices](THIRD_PARTY_NOTICES.md). In particular, review PyMuPDF's
current licensing terms before redistributing the application or using it in a
commercial product.
