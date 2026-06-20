# User Manual

A task-oriented guide to the **My-Second-Brain web app** — what you can do with it
and how to do each thing well. For install, launch, configuration keys, and
troubleshooting, see the [README](README.md); this manual focuses on **workflows
in the app**.

> Keep this manual current. When the app's features, workflows, config, page
> formats, or supported sources change, update the matching section here so the
> manual never drifts from the app.

---

## 1. The mental model

The app turns a pile of local materials into a maintained, interlinked Markdown
wiki. The division of labor is the whole point:

- **You** curate sources, ask questions, and decide what matters.
- **The LLM** writes and maintains the entire `wiki/` layer — every page, summary,
  cross-reference, and index entry. You almost never hand-edit wiki pages.

Three layers, which you should never confuse:

| Layer | What it is | Who edits it |
| ----- | ---------- | ------------ |
| **Raw sources** (`raw/`) | The files you ingest, copied in verbatim. The source of truth. | You (by ingesting). Immutable afterwards. |
| **Wiki** (`wiki/`) | LLM-generated concept/source pages, plus `index.md`, `log.md`, `overview.md`. | The LLM. |
| **Schema** (`wiki/purpose.md`, `wiki/schema.md`) | The instructions the compiler obeys. | You + the LLM, occasionally. |

Unlike classic RAG (which re-reads raw chunks on every question), the knowledge is
**compiled once and kept current**, so answers compound over time.

---

## 2. Core concepts you need before starting

### The vault
A "vault" is the directory containing a `.llmwiki/` folder — created when you run
`llmwiki init`. The app serves one vault: launch it from the vault root.

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

Select a scope in the sidebar tree (or open a section's hub), and it obeys one
**prefix rule**: a scope sees a page iff the scope is a prefix of the page's
section. General sees everything; `academic` sees every course; a course sees only
itself. To **widen**, pick a parent scope. Scope *is* access — there's no separate
"share" mechanism. `academic` / `non-academic` are just seeded conventions; any
depth works.

### Getting around
A persistent **top bar** is your constant frame of reference on every view:
- the **logo** (left) returns to the home page;
- the **breadcrumb** shows where you are (e.g. *General › Academic › Ask*), and each
  step is clickable to jump up the tree;
- the **scope chip** (right) shows the section your operations run over, with **✕**
  to reset to General — so the scope behind Ask / Lint / Ingest is always visible.

Navigation is uniform: sidebar pages, breadcrumb steps, in-page `[[wikilinks]]`, and
Lint references all click through the same way. A link to a page that isn't in your
wiki shows a brief notice instead of silently doing nothing. On a phone the sidebar
collapses into a **☰ menu** in the top bar; it slides in over the content and closes
when you pick something, tap away, or press Esc.

### Page types (all under `wiki/`, all LLM-owned)
| Page | Purpose |
| ---- | ------- |
| `concepts/<section>/<slug>.md` | One concept: definition, theorems, notation, formulas, proof ideas, examples. |
| `sources/<section>/<slug>.md` | One ingested source: summary + the concepts it grounds. |
| `queries/<slug>.md` | A saved answer. |
| `index.md` | Auto-regenerated navigation catalog. **Never hand-edit.** |
| `log.md` | Append-only, greppable operation timeline. **Never hand-edit.** |
| `overview.md` | Narrative orientation, refreshed on ingest. |
| `purpose.md`, `schema.md` | The schema layer, fed into every LLM call. |

### Provenance
Every concept page carries a `sources:` list tracing back to a source page, which
traces back to a raw file. Lint enforces this — it's what makes answers trustworthy
and auditable.

---

## 3. Getting set up (quick recap)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install ".[web]"
llmwiki set-key openai sk-...        # store the key once (~/.config/llmwiki/.env)
llmwiki init                         # scaffold a vault here
llmwiki                              # launch the app → http://127.0.0.1:8000
```

A key is needed for **Ask**, **Ingest**, and **deep Lint**; browsing, search, and
structural lint work offline. Full details (key persistence, hardened install,
provider switch) are in the [README](README.md#run-the-app).

---

## 4. Workflows

Each is a realistic task done **in the app**, scoped to the section shown in the
top-bar scope chip (set it from the sidebar tree or a section hub).

### W1 — Start a knowledge base
Run `llmwiki init` in an empty folder, then launch the app. You get an empty vault
(seeded `purpose.md` / `schema.md` / `overview.md` / `index.md` / `log.md`). Pick
**General** in the sidebar and start ingesting.

### W2 — Build up a course (academic branch)
Open the **Academic** hub and **+ New course** (e.g. `multivariable-calculus`), or
just ingest into it and it's created on first use. Select the course scope, then use
the **Ingest** panel to upload lecture PDFs/slides one at a time. Each ingest
writes/merges concept pages, writes the source page, refreshes `overview.md`,
regenerates `index.md`, and logs the operation. Re-ingesting an edited file
**merges** new material rather than duplicating it. Then switch to **Ask** to study:
*"state the chain rule and its proof idea."* For proof-heavy courses the schema
preserves definitions, theorem codes, notation, and LaTeX faithfully.

### W3 — Personal / free-form knowledge (non-academic)
Select **Non-academic** (or General) and ingest articles, notes, or URLs via the
Ingest panel. Then ask, e.g. *"what have I read about habit formation?"*
Non-academic pages stay citation-aware and wikilinked without the strict academic
schema.

### W4 — Ingest any supported source type
The Ingest panel accepts a **URL** or one-or-more **uploaded files**:

| Source | Notes |
| ------ | ----- |
| Markdown / text | Fastest path; no vision. |
| Text PDF | Text extracted with PyMuPDF. |
| Scanned / math PDF | Auto-uses vision below `pdf_vision_min_chars_per_page`. |
| Word `.docx` / PowerPoint `.pptx` | |
| Image | Transcribed by vision; the file is copied into `raw/assets/`, embedded in the source page, and recorded under `assets:` provenance. |
| Web URL | Fetched and cleaned to Markdown. |

Each source lands in your current scope. Multiple files are processed one at a time
with a ✓/✗ per file.

### W5 — Ask questions and let answers compound
Use the **Ask** panel; answers come only from the wiki, with citations to the pages
used. Attach files to give the model **one-off context** for a single answer — those
attachments are *not* written to the wiki. A good answer is itself knowledge: file
it back into the wiki so explorations accumulate instead of vanishing.

The app **checks the citations**: if an answer references a page that doesn't exist
in your wiki, it shows a caution note listing those pages — that claim isn't backed
by a source, so treat it skeptically. Grounded answers cite only real pages.

### W6 — Fast keyword search
The search box does BM25-lite ranking over concept pages — instant and free (no
key). Use it to locate pages before asking a full question, or when you don't need
synthesis.

### W7 — Health-check and grow the wiki
The **Lint** view runs structural checks (missing `sources:` provenance, unresolved
source refs, dangling `[[wikilinks]]`, orphan pages). Turn on **deep** for an LLM
pass that flags contradictions / missing concepts / stale claims and **suggests
growth**: missing cross-references, new questions, sources to seek, and data gaps.
Suggestions only — the app doesn't browse the web itself.

### W8 — Manage courses and sections
From any section hub: **+ New course / + New section** scaffolds a branch; the **🗑**
on a card deletes one (removes its `concepts/` and `sources/` directories after a
confirmation). The seeded `academic` / `non-academic` branches are protected. Names
keep their casing and non-Latin characters (`example-course`, `线性代数`).

### W9 — Read and navigate in Obsidian
Open the `wiki/` folder as an Obsidian vault for: the **graph view** (hubs,
clusters, orphans), **`[[wikilinks]]`**, **Marp** decks (with the plugin),
**Dataview** tables from page frontmatter, and inline **images** (stored in
`raw/assets/`).

### W10 — Track what happened, when
`wiki/log.md` is an append-only timeline; each entry is a greppable heading like
`## [2026-06-16] ingest | Lecture 3`. Read it in the app, in Obsidian, or:
```bash
grep '^## \[' wiki/log.md | tail -10
```
Don't edit it by hand.

### W11 — Switch providers or tune retrieval
Edit `.llmwiki/config.toml` (then relaunch):
```toml
[settings]
provider = "anthropic"              # or "openai" (default)
default_section = "non-academic"
search_top_k = 8                    # pages retrieved per question
context_token_budget = 60000        # max context tokens for Ask/Lint
request_timeout = 60.0              # seconds before a provider call times out
max_retries = 2                     # retries for transient provider failures
```
Set the matching env key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). Keys never go in
the config. See [README → Configuration](README.md#configuration) for model overrides.

---

## 5. Best practices

- **Ingest one source at a time and stay involved** — read the summary, check the
  updated pages, then ingest the next. You curate; the LLM files.
- **Let the LLM own `wiki/`.** Don't hand-edit concept/source pages; re-ingest or
  ask instead. Never edit `index.md` or `log.md` (they're regenerated/appended).
- **Save answers worth keeping** so explorations compound instead of vanishing.
- **Lint periodically**, especially deep lint after a batch of ingests, to catch
  contradictions and find the next things to read.
- **Keep raw sources immutable** — they're your audit trail. Edit the source file
  and re-ingest if something changed upstream.

---

## 6. Troubleshooting

Common issues (API key not set, `model_not_found`, `command not found: llmwiki`,
`ModuleNotFoundError`, flaky `pip`) are covered in
[README → Troubleshooting](README.md#troubleshooting).

---

## 7. Keeping this manual accurate

This manual tracks the app. Whenever you (or an assistant) change a feature,
workflow, config key, page format, or supported source type, update the relevant
workflow above in the **same change**. The README and this manual should always
agree with the app.
