# My Second Brain by YFW — User Manual

**English** · [简体中文 →](USER_MANUAL.zh-CN.md)

This manual covers installation, browser and CLI workflows, configuration,
storage, privacy, and troubleshooting. The Python distribution is
`my-second-brain-by-yfw`; its import namespace, command, and configuration directory
remain `llmwiki`.

## Contents

1. [Install, initialize, and launch](#install-initialize-and-launch)
2. [How the app works](#how-the-app-works)
3. [Use the browser interface](#use-the-browser-interface)
4. [Understand and manage scopes](#understand-and-manage-scopes)
5. [Add and compile sources](#add-and-compile-sources)
6. [Use Workspace and Search](#use-workspace-and-search)
7. [Read pages, Ask, and use overviews](#read-pages-ask-and-use-overviews)
8. [Review and delete content](#review-and-delete-content)
9. [Customize scope instructions](#customize-scope-instructions)
10. [Provider keys and models](#provider-keys-and-models)
11. [Configuration reference](#configuration-reference)
12. [Command-line reference](#command-line-reference)
13. [Storage, backup, and Obsidian](#storage-backup-and-obsidian)
14. [Privacy and security](#privacy-and-security)
15. [Troubleshooting and limitations](#troubleshooting-and-limitations)

## Install, initialize, and launch

Use Python 3.11 or newer. The supported public workflow installs from a cloned
repository; no package-index installation is assumed.

If this environment already has the previous `second-brain-by-yfw` distribution
installed, remove it before installing the renamed distribution:

```bash
python -m pip uninstall second-brain-by-yfw
```

Run the uninstall first because both distributions provide the same `llmwiki`
package and command.

On macOS or Linux:

```bash
git clone https://github.com/EricWcr7/My-Second-Brain-by-YFW.git
cd My-Second-Brain-by-YFW
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

On Windows PowerShell:

```powershell
git clone https://github.com/EricWcr7/My-Second-Brain-by-YFW.git
cd My-Second-Brain-by-YFW
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

Replace the key placeholder and never commit the result. If you prefer an
environment variable, export `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` before
launching and skip `set-key`.

`llmwiki init .` is idempotent: it creates missing directories and seed files
without replacing existing content. A vault is any directory containing
`.llmwiki/`. Commands look upward from the current directory for that marker, so
they also work from vault subdirectories.

Running `llmwiki` binds to `127.0.0.1:8000`, opens a browser, and shows the
Welcome screen. Select **Enter workspace**. For a headless launch or another
port, use:

```bash
llmwiki serve --port 8080 --no-open
```

Keep the loopback host unless you have added an external authentication and
authorization layer. The app itself has none.

## How the app works

The app compiles source material into a persistent Markdown knowledge base:

```text
files or URLs
    ↓ normalize and analyze
stored source + generated source page
    ↓ extract and merge concepts
linked concept pages
    ↓ retrieve within the active scope
Search, Ask, Review, and overviews
```

### Vault layers

| Layer | Purpose |
| --- | --- |
| `raw/` | Local copies of ingested files and images |
| `wiki/` | Concepts, source pages, saved CLI answers, overviews, index, and log |
| `.llmwiki/` | Settings, ingest state, caches, optional vectors, and instruction overrides |

Generated pages use YAML frontmatter, standard Markdown, `[[wikilinks]]`, and
LaTeX math. Manual edits are possible, but later ingest can merge or replace
generated content. For repeatable changes, update the source or its instructions
and compile again.

### Provenance and grounding

Concept pages list source-page slugs in `sources:` metadata. Source pages point
to a stored raw file or URL. Ask validates each cited `[[slug]]` and warns when a
page does not exist.

Citation validation proves that the page exists, not that it logically supports
every claim. Check the referenced page and original source when accuracy matters.

### Local-first, not fully offline

The vault persists on your machine, but configured model services receive data
needed for AI operations:

- Add source sends normalized text for analysis and generation. Images and
  sparse/scanned PDFs can send original bytes for vision transcription.
- Ask sends the question, retrieved wiki pages, and temporary attachment text or
  vision input.
- Deep Review and overview regeneration send relevant wiki content.
- Semantic search sends page chunks and search queries to the embeddings endpoint.

Browsing, title/slug matching, BM25 Search, and structural Review work without a
provider key.

## Use the browser interface

The desktop navigation contains:

- **Workspace** — scoped search, page lists, and common actions.
- **Ask** — a grounded question with optional temporary files.
- **Review** — structural checks and optional model-assisted review.
- **Add source** — compile files or a URL.
- **Search** — open the command palette.

The header shows the active **Scope**, breadcrumbs, provider readiness, and the
theme control. The Scope menu opens the overview, overview regeneration, scope
settings, and scope management. The selected scope and theme are stored in
browser local storage. On narrow screens, primary navigation moves to the bottom
and the rail becomes a drawer.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Cmd+K` / `Ctrl+K` | Open Search |
| `/` | Focus Workspace search when another field is not active |
| `Enter` | Open the first Search result or action |
| `Esc` | Clear or close Search; close the mobile drawer |

## Understand and manage scopes

A scope is stored as a slash-separated section path. Visibility follows a prefix
rule:

```text
General                         sees every page
academic                        sees the whole academic branch
academic/example-course         sees only that child scope
projects                        sees projects and every child below it
```

Scopes organize navigation and retrieval. They are not accounts or permission
boundaries.

### Select or create a scope

1. Open **Scope → Manage scopes**.
2. Select an existing name, or enter a new **Name** and choose its **Parent**.
3. Select **Create scope** when adding one.

Names preserve Unicode and letter case. Runs of spaces or punctuation become
hyphens in the section path, and duplicate checks are case-insensitive. Opening
a page also switches the active scope to that page's section. Select `General`
to widen retrieval to the whole vault.

`General` and the seeded `Academic` branch are protected from deletion. The
current UI treats children of `Academic` as leaves; other branches can be nested.
Create a destination scope before using Add source.

## Add and compile sources

Open **Add source**, choose **File** or **URL**, confirm the destination, and
select **Compile**. Optional Compilation guidance applies to each item in that
batch. Multiple files run sequentially.

Possible results are:

- **Success** — source and concept pages were written.
- **Skipped** — identical intact content already exists in that scope.
- **Warning** — the core write succeeded, but a follow-up such as indexing or an
  overview refresh failed.
- **Failure** — that item was not compiled; later items continue.

### Supported input

| Input | Extensions or form | Notes |
| --- | --- | --- |
| Markdown / text | `.md`, `.markdown`, `.txt` | Read directly |
| PDF | `.pdf` | PyMuPDF text extraction; sparse/scanned pages use vision |
| Word | `.docx` | Paragraph, heading, and table-cell text |
| PowerPoint | `.pptx` | Text frames read slide by slide |
| Image | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff` | Provider vision; stored under `raw/assets/` |
| Web page | HTTP or HTTPS URL | Readable body extraction; access walls and client-only pages may fail |

Non-image files are copied to `raw/sources/`. A same-named file with different
bytes receives a checksum suffix. URLs remain URLs in provenance; normalized
content is cached under `.llmwiki/`.

Duplicate detection uses content plus destination scope and also checks that the
earlier generated pages remain present. To compile again, add non-empty guidance,
delete a generated page, or use `llmwiki ingest SOURCE --force`. CLI `--vision`
forces PDF vision transcription.

Large sources are divided according to `ingest_segment_max_tokens`. Wiki pages
are committed only after all segments succeed, although a raw copy or normalized
cache may already exist. Vector and overview updates are best-effort follow-ups;
retry them with `llmwiki reindex` or **Regenerate overview**.

## Use Workspace and Search

Workspace lists actions and pages in the active scope. Typing filters by title
and slug immediately and requests ranked concept results. **Search** or
`Cmd/Ctrl+K` opens the same scoped results in a command palette.

BM25 keyword ranking is always available. Semantic vectors participate when all
of these are true:

1. `hybrid_search = true`.
2. The `[search]` extra is installed.
3. An embeddings key or compatible endpoint is configured.
4. The embeddings endpoint can build the selected model's vector index.

Install the extra from the checkout:

```bash
python -m pip install ".[web,search]"
```

After ingest, the app indexes only the concept pages that ingest touched. Before
semantic Search or Ask, it reconciles LanceDB with concept Markdown in the
requested scope and descendants. Missing or changed chunks are embedded and
deleted pages are removed, including changes arriving through Git or another
worktree. An unchanged query still embeds the query itself but does not re-embed
page content.

The first semantic query after filesystem changes can take longer and sends
changed concept chunks in that scope to the configured embeddings endpoint. Set
`hybrid_search = false` to disable synchronization. If synchronization fails,
retrieval logs one warning and returns BM25 results. Source pages may still appear
through local title/slug matching. If expected results are missing, widen the
active scope first.

Run `llmwiki reindex` to build the entire vault before the first query or repair
it explicitly. Use one vector-writing llmwiki process per vault at a time.
Coordination is process-local, so simultaneous web and CLI writers can repeat
embedding work or briefly leave stale derived rows; the next semantic query
reconciles them.

## Read pages, Ask, and use overviews

Concept and source pages render Markdown, KaTeX math, and clickable wikilinks. A
missing wikilink is marked rather than followed silently.

Each scope has a narrative overview. Open **Scope → Overview** to read it and use
**Regenerate overview** to refresh the active scope. Ingest attempts to refresh
the destination and its ancestors. Deletion does not rewrite all surviving
overviews, so regenerate any parent that still mentions removed material.

### Ask

1. Select the intended scope.
2. Open **Ask** and enter a question.
3. Optionally attach files for one request.
4. Select **Ask the model**.

Ask retrieves concept pages, fits them into the context budget, and sends the
result to the main provider. With `rerank = true`, an extra call reorders a wider
candidate set first. Attachments use the ingest loaders but are temporary: they
are not copied into `raw/` or written into the wiki, although their content is
sent to the provider.

The browser does not save answers. Use `llmwiki query --save` to create a file
under `wiki/queries/`. The CLI also supports `--format prose`, `table`, or
`slides`.

## Review and delete content

Structural Review reports concepts without provenance, missing source records,
dangling wikilinks, and orphan concepts. It needs no key. **Deep review** adds a
model pass for contradictions, gaps, stale material, and suggested follow-up;
it does not browse the web or modify pages.

Deletion is permanent, so back up important material first.

- Deleting a concept removes that page and its vectors. Its source ledger remains,
  making the source eligible to compile again.
- Deleting a source removes its source page, matching ingest record, normalized
  cache, and app-owned raw file. It removes same-scope provenance and deletes a
  concept left with no sources.
- Deleting an unprotected scope removes descendant concepts and sources, related
  state/cache/raw files, overviews, instruction overrides, and vectors. Type the
  displayed label exactly to confirm.

Links elsewhere are not rewritten. Run Review and regenerate affected overviews
after deletion.

## Customize scope instructions

Open **Scope → Scope settings** to inspect or edit six instruction components:

- **Purpose**
- **Schema**
- **Ingest · analysis**
- **Ingest · generation**
- **Answer · Ask**
- **Lint · deep review**

`General` is the shared baseline. Each other scope either has its own override or
falls directly back to General; it does not inherit from its nearest parent.
Operation baselines live under `.llmwiki/prompts/`, document baselines in
`wiki/purpose.md` and `wiki/schema.md`, and scope overrides under
`.llmwiki/sections/`.

**Save** writes the editor text, **Undo** discards unsaved edits, **Copy** copies
the text, and **Reset to general** deletes a scope override. The multi-scope Save
control writes the same component to each selected scope. Prompt changes can
materially change generated pages and answers, so test one change on a small
source or question before applying it widely.

## Provider keys and models

The main provider controls ingest, Ask, deep Review, and overview generation.
Choose it in `.llmwiki/config.toml`:

```toml
[settings]
provider = "openai"      # or "anthropic"
```

Store or inspect keys:

```bash
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki set-key anthropic YOUR_ANTHROPIC_API_KEY
llmwiki set-key --show
```

Stored keys are plaintext at `${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env` with
requested POSIX mode `0600`; `--show` masks them. A stored value overrides the
same variable inherited from the shell. Do not store a key if you want the shell
environment to remain authoritative, and restart the server after key changes.

When `compile_model` and `cheap_model` are omitted, each provider supplies its
configured defaults. Override a model only with one your account can access and
that supports the API features used by the app.

Embeddings are independent of the main provider. Semantic search uses an
OpenAI-compatible endpoint configured by `embed_base_url`,
`embed_api_key_env`, and `embed_model`. Anthropic can power the main workflow
while Search remains BM25-only or uses a separately configured embeddings service.

## Configuration reference

Edit `[settings]` in `.llmwiki/config.toml` and restart the server.

| Setting | Default | Effect |
| --- | --- | --- |
| `provider` | `"openai"` | Main provider: OpenAI or Anthropic |
| `compile_model` | provider default | Model for ingest, Ask, deep Review, and overviews |
| `cheap_model` | provider default | Reserved lower-cost model setting |
| `default_section` | `""` | CLI ingest destination; empty means General |
| `search_top_k` | `8` | Concept pages kept for answer context |
| `context_token_budget` | `60000` | Approximate answer/review context ceiling |
| `hybrid_search` | `true` | Enables best-effort vectors in addition to BM25 |
| `embed_base_url` | unset | Compatible embeddings base URL; unset uses OpenAI |
| `embed_api_key_env` | `"OPENAI_API_KEY"` | Environment variable for embeddings auth |
| `embed_model` | `"text-embedding-3-small"` | Embedding model used across scopes |
| `vector_top_n` | `40` | Vector chunks considered before aggregation/fusion |
| `rrf_k` | `60` | Reciprocal Rank Fusion constant |
| `rerank` | `false` | Adds a model relevance pass before Ask context selection |
| `rerank_candidates` | `20` | Candidate pool used when reranking |
| `chunk_max_chars` | `1500` | Maximum characters before embedding sub-splitting |
| `ingest_segment_max_tokens` | `60000` | Approximate maximum source size per ingest segment |
| `pdf_vision_min_chars_per_page` | `100` | PDFs below this text density use vision |
| `request_timeout` | `300.0` | Normal provider timeout in seconds |
| `ingest_request_timeout` | `3600.0` | Per-request timeout during ingest |
| `max_retries` | `2` | SDK retries for transient provider failures |

After changing the embedding model or installing the search extra, the next
semantic operation builds the matching index automatically. Run `llmwiki reindex`
to do so in advance, or `llmwiki reindex --force` to re-embed unchanged pages.
Enabling reranking adds latency and one model call per Ask; failure falls back to
the retrieval order.

## Command-line reference

| Command | Purpose and important options |
| --- | --- |
| `llmwiki` | Launch the browser app |
| `llmwiki init [PATH]` | Create missing vault directories and seeds without overwriting content |
| `llmwiki ingest SOURCE` | Compile one file or URL; `--section`, `--vision`, `--force` |
| `llmwiki query QUESTION` | Ask; `--section`, `--save`, `--format prose\|table\|slides` |
| `llmwiki search QUERY` | Search concepts; `--section`, `--top-k` |
| `llmwiki lint` | Structural Review; optional `--deep` and `--section` |
| `llmwiki overview` | Regenerate General or a specified `--section` overview |
| `llmwiki reindex` | Update semantic vectors; `--force` re-embeds unchanged pages |
| `llmwiki set-key` | Store a key; `--show` lists masked stored values |
| `llmwiki serve` | Launch with `--host`, `--port`, and `--no-open` controls |

Examples:

```bash
llmwiki ingest notes.md --section projects/learning-notes
llmwiki ingest scanned-handout.pdf --section projects/learning-notes --vision --force
llmwiki query "How should I schedule retrieval practice?" --section projects/learning-notes --save --format table
llmwiki search "spaced repetition" --section projects/learning-notes --top-k 5
llmwiki lint --section projects/learning-notes --deep
llmwiki overview --section projects/learning-notes
llmwiki reindex --force
```

Saved queries go to `wiki/queries/`; they are not included in the browser page
list or generated index. Saved `slides` output is Marp-style Markdown.
`llmwiki lint` exits with status 1 only when an error is present.

## Storage, backup, and Obsidian

| Path | Contents |
| --- | --- |
| `raw/sources/` | Copied non-image files |
| `raw/assets/` | Ingested images |
| `wiki/concepts/<section>/` | Generated concepts |
| `wiki/sources/<section>/` | Source and provenance pages |
| `wiki/queries/` | CLI answers saved with `--save` |
| `wiki/overview.md` | General overview |
| `wiki/overviews/<section>.md` | Scope overviews |
| `wiki/index.md` | Generated catalog |
| `wiki/log.md` | Append-only operation journal |
| `wiki/purpose.md`, `wiki/schema.md` | General document baselines |
| `.llmwiki/config.toml` | Vault settings, never API keys |
| `.llmwiki/state.json` | Ingest checksum and provenance ledger |
| `.llmwiki/normalized/` | Normalized Markdown cache |
| `.llmwiki/lancedb/` | Optional vector index |
| `.llmwiki/prompts/` | Editable General operation prompts |
| `.llmwiki/sections/` | Scope instruction overrides |
| `~/.config/llmwiki/.env` | Stored keys outside the vault |

There is no built-in backup, restore, export, or sync command. Stop the server
and copy the entire vault for an exact backup. The vector index can be rebuilt;
the raw material, state ledger, settings, and overrides are needed for the most
complete continuation. Recreate provider keys separately.

Open the **vault root** in Obsidian. Generated pages are under `wiki/`, while
image links can target `raw/assets/`. Markdown and wikilinks work directly;
Marp or Dataview content needs the corresponding plugin. Treat the generated
index, log, and overviews as app-managed.

## Privacy and security

- Never put keys in vault configuration, documentation, Git, screenshots, or
  issue reports.
- A key passed on the command line can remain in shell history. Prefer an
  environment variable or protected secret entry when appropriate.
- Stored keys remain plaintext even though POSIX permissions are restricted.
- Review provider data handling before ingesting sensitive material.
- `raw/`, `wiki/`, and override files can contain source text or instructions.
  Inspect `git status` and ignore rules before committing any initialized vault.
- Keep the default loopback host. Scopes do not provide access control.

The bundled `brain-network.png` illustration was created by EricWcr7 and is
distributed under the repository's [MIT License](LICENSE). Third-party fonts and
libraries keep their own terms; see [Third-Party Notices](THIRD_PARTY_NOTICES.md).
PyMuPDF licensing deserves separate review before redistribution or commercial
use.

## Troubleshooting and limitations

| Symptom | What to check |
| --- | --- |
| `command not found: llmwiki` | Activate the virtual environment used for installation. |
| “No llmwiki vault found” | Run `llmwiki init PATH`, then work there or below it. |
| Web dependency error | From the checkout, run `python -m pip install ".[web]"`. |
| App shows **Local only** | Set the key matching `provider`, restart, and inspect `llmwiki set-key --show`. |
| An exported key appears ignored | A stored value overrides it; update the stored key or remove that entry. |
| Model access error | Choose a compatible model available to the configured account. |
| Unsupported source | Use a listed extension or an HTTP(S) URL. |
| Source is skipped | Add guidance, remove a generated page, or use CLI `--force`. |
| Scanned PDF is incomplete | Retry with CLI `--vision` or adjust the vision threshold. |
| Ingest is slow | Large or vision-heavy sources may require many calls; split the source or adjust the ingest timeout. |
| No semantic results | Install `[search]`, configure embeddings, then run `llmwiki reindex`; BM25 remains available. |
| Search or Ask misses pages | Widen the active scope. |
| Index or overview warning after ingest | Core pages were written; reindex or regenerate the overview separately. |
| Port 8000 is busy | Run `llmwiki serve --port 8080 --no-open`. |
| Production frontend is missing | Run `make web-install && make web-build`, then restart. |

Current limitations include single-user operation without built-in authentication;
no bulk-directory ingest, archive import, backup, restore, export, or sync command;
slug-based navigation that can be ambiguous when slugs repeat; text-focused DOCX
and PPTX extraction; and URL extraction failures behind access walls or
client-side rendering. Generated knowledge can become stale. Recompile changed
sources and run Review periodically.
