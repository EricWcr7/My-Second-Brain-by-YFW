# My Second Brain — User Manual

**English** · [简体中文 →](USER_MANUAL.zh-CN.md)

This manual explains how to use and administer My Second Brain. The
[README](README.md) introduces the project and gets the app running; this guide
covers the complete browser workflow, the CLI, configuration, storage, privacy,
and troubleshooting.

The product is called **My Second Brain**. Its Python package and command-line
program are called `llmwiki`. UI labels appear in **bold** so they are easy to
match to the app.

## Contents

1. [How the app works](#how-the-app-works)
2. [Start the app and enter the workspace](#start-the-app-and-enter-the-workspace)
3. [Understand and manage scopes](#understand-and-manage-scopes)
4. [Add and compile sources](#add-and-compile-sources)
5. [Use Workspace and Search](#use-workspace-and-search)
6. [Read pages and overviews](#read-pages-and-overviews)
7. [Ask questions](#ask-questions)
8. [Review wiki health](#review-wiki-health)
9. [Delete pages and scopes](#delete-pages-and-scopes)
10. [Customize Scope settings](#customize-scope-settings)
11. [Use Solver](#use-solver)
12. [Provider keys and models](#provider-keys-and-models)
13. [Configuration reference](#configuration-reference)
14. [Command-line reference](#command-line-reference)
15. [Storage, backup, and Obsidian](#storage-backup-and-obsidian)
16. [Privacy and security](#privacy-and-security)
17. [Troubleshooting](#troubleshooting)
18. [Current limitations](#current-limitations)

## How the app works

My Second Brain compiles source material into a persistent Markdown knowledge
base. Its basic flow is:

```text
files or URLs
    ↓ normalize and analyze
raw material + generated source page
    ↓ extract and merge concepts
linked concept pages
    ↓ retrieve within the active scope
Search, Ask, Review, overviews, and Solver
```

### The vault

A **vault** is any directory containing `.llmwiki/`. Run `llmwiki init` to create
one. All commands search the current directory and its parents for that marker,
so you can run them from the vault root or a subdirectory.

The vault has three main layers:

| Layer | Purpose | Normal owner |
| --- | --- | --- |
| `raw/` | Local copies of ingested files and images | You supply the material; the app manages its stored copy |
| `wiki/` | Generated concepts, source pages, overviews, index, and log | The app and its configured LLM |
| `.llmwiki/` | Configuration, ingest state, caches, vectors, overrides, and Solver sessions | The app |

Concept and source pages use YAML frontmatter, standard Markdown,
`[[wikilinks]]`, and `$...$` or `$$...$$` LaTeX math. Manual edits are possible,
but a later compilation may merge or replace generated content. Prefer changing
the source, compilation guidance, or Scope settings, then compiling again.

### Provenance and grounding

Every generated concept page should list one or more source-page slugs in its
`sources:` metadata. A source page points to the stored raw copy or source URL. Ask
and Solver answers use `[[slug]]` citations; the app checks that each cited slug
exists and warns when it does not.

That check verifies **existence**, not whether a cited page logically supports
every claim. Read the referenced page and its source when the distinction matters.

### Local-first, not fully offline

The vault persists on your machine. AI-powered work still sends selected content
to a configured provider:

- Add source sends normalized source content for analysis and generation. Images
  and scanned/sparse PDFs first send the original file bytes for vision
  transcription.
- Ask sends the question, retrieved wiki pages, and any temporary attachments;
  image or scanned-PDF attachments can also send original bytes for vision.
- Deep Review and overview regeneration send relevant wiki content.
- Semantic search sends page chunks and queries to the embeddings endpoint.
- Solver sends the conversation, newly retrieved course pages, and attachments.

Browsing, local title/slug matching, BM25 keyword search, and structural Review
can work without an API key.

## Start the app and enter the workspace

Follow the [README quick start](README.md#quick-start) for installation. Then run
this command from a vault or one of its subdirectories:

```bash
llmwiki
```

The server binds to `127.0.0.1:8000`, opens a browser, and shows **Welcome**.
Select **Enter workspace** to open the main application. The brand link returns
to Welcome; it does not reset the current scope.

To change launch behavior, use the hidden `serve` alias:

```bash
llmwiki serve --port 8080 --no-open
llmwiki serve --host 127.0.0.1 --port 8080
```

Avoid `--host 0.0.0.0` unless you deliberately want other machines to reach the
app on a trusted network. The web API has no authentication and includes write
and delete operations.

### Main interface

The desktop rail contains:

- **Workspace** — scoped search, page lists, and common actions.
- **Ask** — one-turn, wiki-grounded questions with optional temporary files.
- **Solver** — persistent course problem-solving sessions; visible only when
  configured.
- **Review** — structural checks and optional LLM review.
- **Add source** — compile files or a URL.
- **Search** — open the command palette.

The header shows the active **Scope**, breadcrumbs, an **AI ready** or **Local
only** status, and the light/dark theme control. Select the Scope control to open:

- **Overview**
- **Regenerate overview**
- **Scope settings**
- **Manage scopes**

The active scope and theme are saved in browser local storage. On narrow screens,
primary navigation moves to the bottom and the rail opens as a drawer.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Cmd+K` / `Ctrl+K` | Open Search from anywhere in the app |
| `/` | Focus the Workspace search field when you are not editing another field |
| `Enter` | Open the first Search result or action |
| `Esc` | Clear/close Search or close the mobile drawer |
| `Cmd+Enter` / `Ctrl+Enter` | Submit a Solver message |

## Understand and manage scopes

A scope is the user-facing organizational unit. On disk it is stored as a
slash-separated **section path**, such as `academic/example-course`.

The visibility rule is a prefix rule:

```text
General                    sees every page
academic                   sees pages in every academic course
academic/example-course          sees pages in example-course only
research                   sees research and any child scopes below it
```

A scope is an organization and retrieval boundary, not an account or permission
boundary.

### Select an existing scope

1. Open **Scope → Manage scopes** or use the **Manage scopes** Workspace action.
2. Select a scope name in the list.
3. The sheet closes and Workspace reloads within that scope.

Opening a concept or source page also changes the active scope to that page's
section. The app remembers the selection for the next browser visit. Select
`General` in Manage scopes whenever you want to search or ask across the entire
vault.

### Create a scope

1. Open **Manage scopes**.
2. Under **Create a scope**, enter a **Name**.
3. Choose a **Parent**.
4. Select **Create scope**.

Use `General` as the parent for a top-level branch such as Research or Personal.
Use `Academic` as the parent for a course. Academic courses are leaves in the
current UI; they cannot receive child scopes. Non-Academic branches may be nested.

Names preserve Unicode and letter case. Runs of spaces or punctuation become
hyphens in the section path. Names are checked case-insensitively for duplicates.

**Add source only lists existing scopes.** Create the destination first; typing a
new name during compilation is not supported.

`General` and the seeded `Academic` scope are protected from deletion. A new
vault contains Academic, but no course, course content, or Solver setup.

## Add and compile sources

Select **Add source** in the rail or choose the matching Workspace action.

### Compile a file or URL

1. Choose the **File** or **URL** tab.
2. For files, drag and drop one or more items or select **choose files**. For a
   web page, paste an HTTP or HTTPS URL.
3. Optionally enter **Compilation guidance** such as “preserve proof steps” or
   “focus on chapter 3.” The same guidance applies to every item in this batch.
4. Check **Scope** and **Destination** carefully.
5. Select **Compile into _scope_**.

Multiple items are processed sequentially to avoid sending a burst of expensive
model requests. Each row finishes with one of four outcomes:

- **Success** — the source page and any generated or updated concept pages were
  written.
- **Skipped** — identical, intact content already exists in that scope.
- **Warning** — the core wiki write succeeded, but a follow-up such as vector
  indexing or overview refresh did not.
- **Failure** — the item was not compiled; other selected items continue.

### Supported source types

| Input | Extensions or form | Loader behavior and caveats |
| --- | --- | --- |
| Markdown / text | `.md`, `.markdown`, `.txt` | Read directly as text |
| PDF | `.pdf` | Extracts text with PyMuPDF; sparse/scanned PDFs switch to provider vision |
| Word | `.docx` | Extracts paragraphs, headings, and table cells; embedded media is not a separate vision input |
| PowerPoint | `.pptx` | Extracts text frames slide by slide; diagrams or images without text may be missed |
| Image | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff` | Uses provider vision; stored under `raw/assets/` |
| Web page | `http://` or `https://` URL | Fetches and cleans the readable page body; paywalls and client-rendered pages may fail |

Non-image local files are copied into `raw/sources/`. If the same filename already
exists with different bytes, the app adds an eight-character checksum suffix.
URLs remain URLs in provenance; their normalized content is cached under
`.llmwiki/`.

### Duplicate and recompile behavior

Duplicate detection uses the file/content checksum plus destination scope. An
unchanged source is skipped only while its source page and all concept pages from
the earlier ingest still exist. A renamed download with identical bytes is still
recognized as a duplicate.

To compile again:

- In the web app, provide non-empty Compilation guidance or delete a generated
  page first.
- In the CLI, use `llmwiki ingest SOURCE --force`.
- Use CLI `--vision` to force vision transcription for a PDF.

### Large sources and commit behavior

Sources larger than `ingest_segment_max_tokens` are divided into deterministic
segments. Each segment runs the analysis and generation passes, and their drafts
are merged into one source record. Concept and source pages are committed only
after every segment succeeds, so a mid-compile model failure does not partially
rewrite the wiki. A raw copy and normalized cache may already have been created.

After the main write, vector indexing and overview regeneration are best-effort.
Their failure appears as a warning and does not roll back the new pages. Retry with
`llmwiki reindex` or **Regenerate overview** as appropriate.

## Use Workspace and Search

Workspace is the command desk for the active scope. With an empty query it shows
common actions and a short list of concepts and sources. Enter text to filter by
title/slug immediately and request ranked concept results from the backend.

The action group contains:

- **Add source**
- **Ask**
- **Review scope**
- **Refresh overview**
- **Manage scopes**

Select **Search** or press `Cmd/Ctrl+K` to open the same scoped results and actions
in a command palette. This is an app-wide shortcut, but its results still obey the
active scope.

### Keyword and semantic ranking

Backend search always builds a BM25 keyword ranking over concept titles and page
content. When all four requirements below are met, it fuses that ranking with
semantic vectors using Reciprocal Rank Fusion:

1. `hybrid_search = true`.
2. The `[search]` extra is installed.
3. An embeddings key or OpenAI-compatible endpoint is configured.
4. A vector index exists for the current `embed_model`.

If any vector component is unavailable, Search quietly returns keyword results.
Install vectors later and run:

```bash
llmwiki reindex
```

Search ranks concept pages semantically. Source pages can still appear through
the Workspace's local title/slug matching.

If results look incomplete, first check the active Scope. Select a parent or
`General` to widen retrieval.

## Read pages and overviews

Concept and source pages render as Markdown with KaTeX math and clickable
`[[wikilinks]]`. The breadcrumb shows the current section. Opening a page updates
the active scope, and selecting a valid wikilink opens the referenced page.

If a wikilink points to a slug that does not exist, the app marks it as missing
and shows a notice instead of navigating silently.

### Overviews

Each scope has a narrative overview. Open **Scope → Overview** to read it. Use
**Regenerate overview** in the Scope menu or **Refresh overview** in Workspace to
rewrite the current scope's overview.

Compiling a source automatically attempts to refresh the destination overview and
every ancestor up to General. Manual regeneration targets only the current scope
and requires the main provider key. An empty General overview can fall back to
the generated catalog in `wiki/index.md`.

Deleting a page or scope does not automatically rewrite every surviving parent
overview. Regenerate the affected parent if its summary still mentions deleted
material.

## Ask questions

Ask produces a single answer from the active scope.

1. Select the intended scope before opening **Ask**.
2. Enter a question, or select one of the example prompts.
3. Optionally use **Attach files** for one-off context.
4. Select **Ask the model**.

The app retrieves concept pages within the scope, fits them into the configured
context budget, and sends them with the question to the main provider. If
`rerank = true`, an extra model call reorders a wider candidate set before the
final context is built.

Ask accepts uploaded files—not URL attachments—and uses the same supported file
types and loaders as Add source. Files are converted to temporary context and are
not copied into `raw/`, written to the wiki, or kept after the request. Their
content is still sent to the provider.

The answer shows:

- rendered Markdown and math;
- a **References** list for real wiki slugs cited by the model; and
- a warning for cited slugs that do not exist.

The web app does not save Ask answers. Use `llmwiki query --save` when an answer
should become a file under `wiki/queries/`.

## Review wiki health

Open **Review** and select **Run checks**. Structural Review needs no API key and
reports:

- concept pages with no `sources:` provenance;
- provenance entries with no matching source page;
- dangling `[[wikilinks]]`; and
- orphan concepts with no inbound links.

Enable **deep review (uses API)** for an additional LLM pass. It may report
contradictions, missing concepts, unclear or stale material, missing
cross-references, questions to investigate, suggested sources, and data gaps.

Deep Review does not search the web or modify pages. Its findings are editorial
suggestions for you to evaluate.

## Delete pages and scopes

Deletion is permanent. Back up important material first.

### Delete one concept page

Open the page and select the trash icon. After confirmation, the app removes the
concept page and its vector entries. Its source ledger remains, but the missing
page makes that source eligible for recompile.

### Delete one source page

Open the source page and select the trash icon. The app removes the source page,
its matching ingest record, normalized cache, and owned raw file. It also removes
that source from same-scope concept provenance and deletes any concept left with
no sources.

Wikilinks elsewhere are not rewritten; Review will report links that now dangle.

### Delete a scope

1. Open **Scope → Manage scopes**.
2. Select the trash icon beside an unprotected scope.
3. Type the displayed scope label exactly.
4. Confirm **Delete scope**.

This removes descendant concept/source pages, matching ledger and cached/raw
files, overviews, instruction overrides, and vector entries. `General` and
`Academic` cannot be deleted.

Solver sessions live separately under `.llmwiki/solver/` and are not part of a
scope deletion. Delete unneeded sessions in Solver as well. If you delete the
configured Solver scope, clear or change `solver_section` and restart; scope
deletion does not update that setting automatically.

## Customize Scope settings

Open **Scope → Scope settings** to edit the LLM instructions for the current
scope. The available cards are:

- **Purpose**
- **Schema**
- **Ingest · analysis**
- **Ingest · generation**
- **Answer · Ask**
- **Solver · problem sets**
- **Lint · deep review**

`General` is the shared **Baseline**. Every other scope shows each card as:

- **Inherited** — uses the General baseline; or
- **Override** — uses text saved specifically for this scope.

Inheritance is deliberately shallow. A scope without its own override falls
straight back to General; it does not inherit from its parent branch.

Card controls behave as follows:

- **Save** stores the current editor text.
- **Undo** restores the last saved text in the editor; it only discards unsaved
  changes.
- **Copy** places the editor text on the clipboard.
- **Reset to general** deletes that scope's override and restores the General
  baseline.
- **Also apply each Save to** writes the same component to every selected scope.

Editing the General baseline changes every scope that still inherits that
component. Prompt changes can materially change generated pages and answers, so
edit one component at a time and test it on a small source or question.

## Use Solver

Solver is a persistent, multi-turn problem-set chat locked to one configured
scope. It is a browser-only workflow.

### Enable Solver

In `.llmwiki/config.toml`, set a non-empty section path and restart the server:

```toml
[settings]
solver_section = "academic/example-course"
```

A fresh vault leaves this setting empty, so Solver is hidden. The sample checkout
already enables it for `academic/example-course`.

### Start and use a session

1. Open **Solver**.
2. Choose a **New session model**. The current code offers **GPT-5.6 Sol** and
   **Claude Fable 5** when their matching keys are available.
3. Select **New session**. The model choice is locked for that session.
4. Enter a **Problem or follow-up**.
5. Optionally attach PDFs or images.
6. Select **Solve** or press `Cmd/Ctrl+Enter`.

Each turn retrieves fresh concept pages from `solver_section`, sends the full
conversation, and produces a worked Markdown solution. Real citations appear in
References; missing slugs produce the same warning as Ask. A provider-generated
**Reasoning summary** appears in a collapsed panel when available. It is not raw
chain-of-thought, and some successful responses have no summary.

### Attachments and persistence

Solver accepts `.pdf`, `.png`, `.jpg`, `.jpeg`, `.gif`, and `.webp`, up to 30 MB
per file. Attachments are not ingested into the wiki, but they are stored with the
session and re-sent as conversation history on later turns. Long sessions with
large attachments can therefore be slow and costly.

Sessions persist under `.llmwiki/solver/` across restarts. Deleting a session
removes its transcript and attached files. If a provider call fails, the attempted
turn is not appended and newly uploaded files for that turn are removed.

Both selectable models use their configured maximum reasoning effort. Model
availability depends on your provider account; the repository's defaults do not
guarantee access.

## Provider keys and models

The main provider controls Add source, Ask, deep Review, and overview generation.
Set it in `.llmwiki/config.toml`:

```toml
[settings]
provider = "openai"      # or "anthropic"
```

Store the matching key:

```bash
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki set-key anthropic YOUR_ANTHROPIC_API_KEY
llmwiki set-key --show
```

`--show` masks stored values. Keys are written as plaintext with file mode `0600`
to `${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env`; they are never written to the
vault config. A stored value overrides a same-named shell environment variable at
startup. If an exported key appears correct but authentication still fails, check
the stored key. Restart the server after changing keys.

When model settings are omitted, the current code defaults to:

| Provider | Compile/answer default | Secondary/cheap default |
| --- | --- | --- |
| OpenAI | `gpt-5.6-sol` | `gpt-5.6-sol` |
| Anthropic | `claude-opus-4-8` | `claude-haiku-4-5` |

Override `compile_model` if your account cannot access the default. For OpenAI,
the replacement must support the Responses API reasoning parameters used by the
app, including `reasoning.effort = "high"`; the current configuration guidance
expects a GPT-5.5+ reasoning model. `cheap_model` is reserved for lower-cost
operations and may not be used by every current path.

Solver model selection is independent of the main `provider`: GPT uses
`OPENAI_API_KEY`, while Claude uses `ANTHROPIC_API_KEY`. Set both keys to offer
both choices.

Embeddings are also independent. Semantic search always uses an OpenAI-compatible
embeddings endpoint configured by `embed_base_url`, `embed_api_key_env`, and
`embed_model`. An Anthropic key can make Ask ready while semantic search remains
in keyword-only mode.

## Configuration reference

Edit `[settings]` in `.llmwiki/config.toml`, then restart the web server. Defaults
below describe a newly initialized vault; the sample checkout overrides some of
them.

| Setting | Default | Effect |
| --- | --- | --- |
| `provider` | `"openai"` | Main chat/compile provider: `openai` or `anthropic` |
| `compile_model` | provider default | Model used for compilation, Ask, deep Review, and overviews |
| `cheap_model` | provider default | Reserved lower-cost model setting |
| `default_section` | `""` | CLI ingest destination when `--section` is omitted, and metadata section for an unscoped saved query; empty means General |
| `search_top_k` | `8` | Concept pages kept for an answer or Solver turn |
| `context_token_budget` | `60000` | Approximate context ceiling for Ask and deep Review |
| `hybrid_search` | `true` | Enables the best-effort semantic path in addition to BM25 |
| `embed_base_url` | unset | OpenAI-compatible embeddings base URL; unset uses OpenAI |
| `embed_api_key_env` | `"OPENAI_API_KEY"` | Environment variable read for embeddings auth |
| `embed_model` | `"text-embedding-3-small"` | Single embedding model used for all scopes |
| `vector_top_n` | `40` | Vector chunks considered before page aggregation/fusion |
| `rrf_k` | `60` | Reciprocal Rank Fusion constant |
| `rerank` | `false` | Adds an LLM relevance pass before Ask context selection |
| `rerank_candidates` | `20` | Wider candidate pool used when reranking |
| `chunk_max_chars` | `1500` | Maximum characters before a page section is split for embeddings |
| `ingest_segment_max_tokens` | `60000` | Approximate maximum source size per compilation segment |
| `pdf_vision_min_chars_per_page` | `100` | PDFs below this extracted-text density use vision |
| `request_timeout` | `300.0` | Provider timeout in seconds for normal operations |
| `ingest_request_timeout` | `3600.0` | Per-request timeout used during Add source / ingest |
| `max_retries` | `2` | SDK retries for transient provider failures |
| `solver_section` | `""` | Fixed Solver scope; empty disables Solver |
| `solver_reasoning_effort` | `"xhigh"` | Effort for legacy sessions without a locked catalog model |
| `solver_request_timeout` | `600.0` | Per-turn Solver timeout in seconds |

After changing `embed_model` or installing `[search]` later, run `llmwiki reindex`.
Turning `rerank` on adds latency and one model call per Ask or Solver turn; if
reranking fails, the normal retrieval order is used.

## Command-line reference

The CLI and web app share the same core pipelines, but their features are not
identical.

| Command | Purpose and important options |
| --- | --- |
| `llmwiki` | Launch the web app |
| `llmwiki init [PATH]` | Create missing vault directories and seed files without overwriting existing content |
| `llmwiki ingest SOURCE` | Compile one file or URL; supports `--section`, `--vision`, and `--force` |
| `llmwiki query QUESTION` | Ask from the terminal; supports `--section`, `--save`, and `--format prose\|table\|slides` |
| `llmwiki search QUERY` | Search concept pages; supports `--section` and `--top-k` |
| `llmwiki lint` | Structural Review; add `--deep` and/or `--section` |
| `llmwiki overview` | Regenerate General or a specified `--section` overview |
| `llmwiki reindex` | Build/update semantic vectors; `--force` re-embeds unchanged pages |
| `llmwiki set-key` | Store a provider key; `--show` lists masked stored keys |
| `llmwiki serve` | Launch with `--host`, `--port`, and `--no-open` controls |

Examples:

```bash
llmwiki ingest lecture.pdf --section academic/example-course
llmwiki ingest scan.pdf --section academic/example-course --vision --force
llmwiki query "Compare open and closed sets" --section academic/example-course --save --format table
llmwiki query "Summarize the course" --save --format slides
llmwiki search "boundary points" --section academic/example-course --top-k 5
llmwiki lint --section academic/example-course --deep
llmwiki overview --section academic/example-course
llmwiki reindex --force
```

Saved queries go to `wiki/queries/`. They are not currently included in the web
page list or generated `wiki/index.md`. The `slides` format writes Marp-style
Markdown with `marp: true` when saved.

`llmwiki lint` exits with status 1 only when it finds an error. Warnings and info
items alone still return status 0.

## Storage, backup, and Obsidian

### Full layout

| Path | Contents |
| --- | --- |
| `raw/sources/` | Copied non-image files |
| `raw/assets/` | Ingested image files |
| `wiki/concepts/<section>/` | Generated concept pages |
| `wiki/sources/<section>/` | Generated source/provenance pages |
| `wiki/queries/` | CLI answers saved with `--save` |
| `wiki/overview.md` | General overview |
| `wiki/overviews/<section>.md` | Per-scope overviews |
| `wiki/index.md` | Regenerated concept/source catalog |
| `wiki/log.md` | Append-only operation journal |
| `wiki/purpose.md`, `wiki/schema.md` | General instruction baseline |
| `.llmwiki/config.toml` | Vault settings, never API keys |
| `.llmwiki/state.json` | Ingest checksum and provenance ledger |
| `.llmwiki/normalized/` | Normalized Markdown cache |
| `.llmwiki/lancedb/` | Optional vector index |
| `.llmwiki/prompts/` | Editable General operation prompts |
| `.llmwiki/sections/` | Per-scope instruction overrides |
| `.llmwiki/solver/` | Solver transcripts and attachments |
| `~/.config/llmwiki/.env` | Persisted API keys outside the vault |

### Backup and restore

There is no built-in export, backup, restore, or sync command. Stop the server and
copy the entire vault directory when you want a complete backup. This preserves
raw files, generated pages, configuration, state, overrides, and Solver sessions.
The global key file is outside the vault and should normally be recreated rather
than copied.

`wiki/` alone is a useful portable reading copy, but it omits raw source files,
ingest state, settings, and Solver sessions. `.llmwiki/lancedb/` is regenerable
with `llmwiki reindex`; the other state may be valuable for exact continuation.

### Use with Obsidian

Open the **vault root** as the Obsidian vault. Generated pages live under `wiki/`,
while image source pages can link to `raw/assets/` outside that directory.
Obsidian understands the Markdown and wikilinks directly. Graph and backlink
views work without changing the files; Marp slides and Dataview queries require
their respective Obsidian plugins.

Treat `wiki/index.md`, `wiki/log.md`, and generated overviews as app-managed.
Manual changes can be overwritten or become inconsistent with the ingest ledger.

## Privacy and security

- Never put API keys in `.llmwiki/config.toml`, documentation, Git, screenshots,
  or issue reports.
- `llmwiki set-key` stores keys outside the vault and requests file mode `0600`
  on POSIX systems, but the values remain plaintext on disk. Windows does not
  enforce Unix ownership bits in the same way.
- Passing a plaintext key directly as a command-line argument can leave it in
  shell history. Prefer a protected secret prompt or temporary environment
  variable if your shell records commands.
- Review your provider's data handling before compiling sensitive material.
- Solver transcripts and attachments persist under `.llmwiki/solver/`.
- A newly scaffolded vault does not comprehensively ignore Solver and vector
  state for Git. Inspect `git status` and your ignore rules before committing a
  vault containing private material.
- `raw/` and `wiki/` may also contain sensitive source text by design.
- Keep the default loopback host unless you have added an appropriate external
  access-control layer. Scopes do not provide authorization.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `command not found: llmwiki` | Activate the virtual environment where the package was installed. |
| “No llmwiki vault found” | Run `llmwiki init PATH`, then work in that directory or a descendant. |
| Web UI dependency error | From the repository root, run `python -m pip install ".[web]"`. |
| App shows **Local only** | Set the key matching `provider`, restart the server, and inspect `llmwiki set-key --show`. |
| Correct exported key still fails | A stored key overrides the shell value; update or inspect the stored key. |
| `model_not_found`, permission, or access error | Set `compile_model` to an accessible compatible model. OpenAI overrides must support the app's Responses API reasoning parameters. |
| Unsupported file type | Use an exact supported extension or an HTTP(S) URL. Rename only when the file format truly matches. |
| Source says skipped | Content is already intact in that scope. Add guidance, delete a generated page, or use CLI `--force`. |
| Scanned PDF is incomplete | Retry through CLI with `--vision`, or raise `pdf_vision_min_chars_per_page`. |
| Add source is slow or times out | Large/vision sources can require many calls. Retry, split a scanned file, or adjust `ingest_request_timeout`. |
| No semantic results | Install `[search]`, configure the embeddings key/endpoint, then run `llmwiki reindex`. Keyword search should still work. |
| Search or Ask misses expected pages | Check Scope first; move to a parent or General. |
| Ingest finished with vector/overview warning | Pages were committed. Run `llmwiki reindex` or regenerate the overview separately. |
| Solver is missing | Set `solver_section` and restart. A fresh vault disables it. |
| Solver model is disabled | Store the environment key named beside that model; existing sessions cannot switch models. |
| Solver rejects an upload | Use PDF or a supported image and keep each file at or below 30 MB. |
| Port 8000 is busy | Run `llmwiki serve --port 8080 --no-open`. |
| `ModuleNotFoundError: llmwiki` after editable install | Reinstall normally: `python -m pip install --force-reinstall --no-deps .` |
| Frontend route returns 404 in a development checkout | Run `make web-install` and `make web-build`, then restart. |

Provider errors are surfaced without raw application tracebacks. A failed Ask or
Solver call does not silently switch providers.

## Current limitations

- The app is single-user and has no built-in authentication or authorization.
- It has no built-in vault archive import, bulk-directory ingest, export, backup,
  restore, or sync workflow.
- Web and CLI capabilities differ: force/vision ingest, saved/formatted answers,
  and reindex controls are CLI-oriented; scope management, Scope settings, and
  Solver are browser-oriented.
- Citation validation checks that a wiki slug exists, not whether a claim is
  entailed by that page.
- Page navigation is slug-based. Identical slugs across scopes or page types can
  resolve ambiguously, so prefer distinct concept/source names.
- DOCX/PPTX loaders focus on extractable text; visual-only content may require a
  separate image or PDF ingest.
- URL extraction can fail for authentication walls, paywalls, anti-bot measures,
  or pages whose content exists only after client-side rendering.
- Add source and Ask do not enforce a dedicated app-level upload-size limit;
  practical limits still come from memory, timeouts, and provider payload rules.
- Generated knowledge can become stale when an upstream source changes. Recompile
  changed material and run Review periodically.
