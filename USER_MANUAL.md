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
| **Wiki** (`wiki/`) | LLM-generated concept/source pages, plus per-section overviews (`overviews/`), `index.md`, `log.md`, `overview.md`. | The LLM. |
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
├── academic              → all courses
│   └── academic/<course> → only that course
└── <your branch>         → a top-level branch you add (e.g. personal, work)
```

Select a scope in the sidebar tree (or open a section's hub) — or just open any
page: the scope follows the page's section. It obeys one **prefix rule**: a scope
sees a page iff the scope is a prefix of the page's section. General sees everything; `academic` sees every course; a course sees only
itself. To **widen**, pick a parent scope. Scope *is* access — there's no separate
"share" mechanism. `academic` is the one seeded convention; add your own top-level
branches (siblings of Academic) from the homepage, and any depth works.

### Getting around
A persistent **top bar** is your constant frame of reference on every view:
- the **logo** (left) returns to the home page;
- the **breadcrumb** shows where you are (e.g. *General › Academic › Ask*), and each
  step is clickable to jump up the tree;
- the **scope chip** (right) shows the section your operations run over, with **✕**
  to reset to General — so the scope behind Ask / Lint / Ingest is always visible.
  The chip tracks the page you're reading, not just section hubs: open a course
  page and the scope becomes that course.

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
| `overview.md`, `overviews/<section>.md` | One narrative overview per section (the General root uses `overview.md`; every other section maps to `overviews/<section-path>.md`). Refreshed on ingest and on demand. |
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

A key is needed for **Ask**, **Ingest**, **deep Lint**, and **semantic search**;
browsing, **keyword** search, and structural lint work offline (hybrid search falls
back to keyword-only). Full details (key persistence, hardened install,
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
the **Ingest** panel to upload lecture PDFs/slides one at a time — the form's
**Destination** picker confirms the course before you submit. Each ingest
writes/merges concept pages, writes the source page, refreshes the section's
overview (and its parents up to General), regenerates `index.md`, and logs the
operation. Re-ingesting an edited file
**merges** new material rather than duplicating it. Re-uploading an *unchanged*
file is skipped while its pages still exist — even a browser-renamed copy like
`lecture (1).pdf` is recognized as the same content. To rebuild pages from
unchanged material, add guidance text (guidance always re-ingests so the pages
can be reshaped) or delete the pages first. Then switch to **Ask** to study:
*"state the chain rule and its proof idea."* Proof-heavy courses (like the seeded
`example-course`) carry their own **Customize** override that preserves definitions,
theorem/lemma codes, notation, proof ideas, and LaTeX faithfully — see **W12**;
other branches use the general default.

### W3 — Personal / free-form knowledge (your own branch)
On the homepage, under **Browse by branch**, click **+ New branch** to add a
top-level branch (e.g. `Personal`) beside Academic — it appears as a new card.
Open it (or General) and ingest articles, notes, or URLs via the Ingest panel.
Then ask, e.g. *"what have I read about habit formation?"* Such branches use the
general schema — citation-aware and wikilinked, without course-specific structure.

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

Each source lands in the **Destination** section shown on the form — pre-set to
your current scope and changeable per submission. Multiple files are processed one
at a time with a ✓/✗ per file.

**Optional guidance.** Below the file/URL inputs is an optional **guidance box** — type
a short instruction for how the model should compile the source ("focus on the proofs",
"only chapter 3", "keep it beginner-friendly"). It steers **both** compile passes (which
concepts get extracted *and* how the pages are written), applies to every file/URL in
that submission, and is recorded in `log.md` for that ingest. Leave it blank for the
default behavior. Guidance never overrides grounding — the model still won't add anything
the source doesn't support.

**Very large files** (e.g. a several-hundred- or 1000-page PDF) are compiled in
**segments** automatically: the source is split on page/heading boundaries into
windows of about `ingest_segment_max_tokens`, each window runs the analysis +
generation passes, and the results **merge into the same section's pages**. You
still upload one file and get one source page and one provenance record — no need
to split the PDF yourself. It just takes proportionally longer (each segment is a
model pass), and ingest runs under the longer `ingest_request_timeout` so a slow
pass isn't cut off the way the shorter interactive timeout would. The compile is
**atomic**: nothing is written until every segment has succeeded, so if an ingest
fails partway (a timeout or model error) the wiki is left exactly as it was — just
re-run it. *Scanned* PDFs that big are still limited by single-call vision
transcription — split those by hand for now.

### W5 — Ask questions and let answers compound
Use the **Ask** panel; answers come only from the wiki, with citations to the pages
used. Attach files to give the model **one-off context** for a single answer — those
attachments are *not* written to the wiki. A good answer is itself knowledge: file
it back into the wiki so explorations accumulate instead of vanishing.

The app **checks the citations**: if an answer references a page that doesn't exist
in your wiki, it shows a caution note listing those pages — that claim isn't backed
by a source, so treat it skeptically. Grounded answers cite only real pages.

For tougher questions you can enable **reranking** (`rerank = true` in
`.llmwiki/config.toml`): after hybrid retrieval pulls a wider pool of
`rerank_candidates` pages, the model reorders them by relevance so the most useful
ones win the answer's limited context budget. It's off by default because it adds
one model call per question; if that call fails the answer simply falls back to the
normal retrieval order.

### W6 — Hybrid search (keyword + meaning)
The search box ranks concept pages by **hybrid retrieval**: BM25 keyword scoring
fused with **semantic vector** similarity via Reciprocal Rank Fusion, so a query
finds the right page even when it shares no words with it (e.g. "rate of change of a
multivariable function" → the *gradient* page). Use it to locate pages before asking
a full question, or when you don't need synthesis. Semantic ranking needs the
`[search]` extra and an embeddings key; without them the box falls back to instant,
free BM25 keyword ranking. New pages are embedded automatically on ingest — run
`llmwiki reindex` to rebuild the vector index from scratch (e.g. after installing
`[search]` later, or changing `embed_model`).

### W7 — Health-check and grow the wiki
The **Lint** view runs structural checks (missing `sources:` provenance, unresolved
source refs, dangling `[[wikilinks]]`, orphan pages). Turn on **deep** for an LLM
pass that flags contradictions / missing concepts / stale claims and **suggests
growth**: missing cross-references, new questions, sources to seek, and data gaps.
Suggestions only — the app doesn't browse the web itself.

### W8 — Manage branches, courses, sections and pages
From the homepage **Browse by branch** section, **+ New branch** adds a top-level
branch (a sibling of Academic). From any section hub, **+ New course / + New
section** scaffolds a child; the **🗑** on a card deletes one after a confirmation
— a *full* wipe that removes its `concepts/` and `sources/` pages **and**
everything filed under it (the ingest ledger records, their cached/raw source
files, and any per-section customizations), so nothing orphaned is left behind.
Re-ingesting after a delete always works regardless: ingest skips a source only
while its pages still exist in the wiki. The seeded `academic` branch
is protected. Names keep their casing and non-Latin characters (`example-course`, `线性代数`).

Single pages can be deleted too: every page's reading view has a **🗑** next to
its concept/source label. Deleting a **concept** removes the page and its
search-index entries — its source can then be re-ingested to rebuild it.
Deleting a **source** is a full teardown: the page, its ingest ledger record,
and its cached and raw files are all removed, the source is scrubbed from the
`sources:` provenance of this section's concepts, and any concept left with no
sources at all is deleted with it (the confirmation dialog and the toast tell
you when that happens). Wikilinks elsewhere that pointed at a deleted page
surface later as Lint warnings rather than being rewritten.

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
default_section = ""                # default scope ("" = General root)
search_top_k = 8                    # pages retrieved per question
context_token_budget = 60000        # max context tokens for Ask/Lint
rerank = false                      # opt-in: LLM reranks retrieved pages before answering (W5)
rerank_candidates = 20              # candidates pulled before reranking down to search_top_k
ingest_segment_max_tokens = 60000   # compile a larger source in segments (W4)
hybrid_search = true                # fuse keyword + vector (false = keyword only)
embed_model = "text-embedding-3-small"  # embedding model used for every section
# embed_base_url = "http://localhost:11434/v1"  # OpenAI-compatible endpoint (e.g. Ollama)
request_timeout = 300.0             # seconds before a provider call times out
ingest_request_timeout = 3600.0     # longer ceiling for ingest only (big/multi-pass sources)
max_retries = 2                     # retries for transient provider failures
# solver_section = "academic/example-course"  # enable the Problem Set Solver, scoped to this section (W14)
solver_reasoning_effort = "xhigh"   # legacy sessions only; new sessions use fixed max effort
solver_request_timeout = 600.0      # per-turn ceiling for solver calls (max effort runs long)
```
Set the matching env key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). Keys never go in
the config. **Semantic search is independent of the chat `provider`** — embeddings
always use an OpenAI-compatible endpoint, so it works on the Anthropic backend too;
install it with `pip install ".[search]"`. After changing `embed_model`, run
`llmwiki reindex` to rebuild the vector index. See
[README → Configuration](README.md#configuration) for the full key list and model
overrides.

### W12 — Customize a branch's LLM instructions
Every section hub has a **Customize** view (also reachable at `#/customize/<section>`).
It exposes the LLM instruction set *for that branch*: the prompt for each operation
— **ingest analysis**, **ingest generation**, **answer**, **solver**, **lint** — plus
the branch's **purpose** and **schema**. Each card shows the text currently in effect with an
**Override / Inherited** badge:

- **Save** writes an override for this branch (the badge flips to *Override*).
- **Reset to general** drops the override so the branch inherits the **general
  default** again.
- **Also apply each Save to** lists the other branches still on the general default
  — check any to apply the same change to several branches at once (leave all
  unchecked to change only this branch).

A branch with no override inherits the general default; there is no walking up parent
sections. This is how a proof-heavy course keeps its math rules while the rest of the
wiki stays general — the seeded `example-course` ships with override prompts/purpose/schema
that preserve definitions, theorem/lemma codes, notation, proof ideas, and LaTeX.
Create another proof course and you can apply the same from this view. Customizing
**General** edits the shared default every uncustomized branch inherits.

### W13 — Browse and refresh a section's overview
Every section hub — **General**, each branch, each course — has a **Browse overview**
button that opens an LLM-written orientation to *that* section: what it covers, how
its main ideas connect, and where to start, with `[[wikilinks]]` into the pages. The
General root's overview is also the app's home page.

Overviews are kept current for you: every **Ingest** refreshes the overview of the
section you added to **and all of its parents up to General** (so a branch or the home
overview never goes stale just because you filed into a course beneath it). To rebuild
one yourself — say after deleting a sub-section, or to retry — open the section's hub
and click **Regenerate overview**. From the terminal, `llmwiki overview --section
academic/example-course` does the same (omit `--section` for the General overview). Overviews
live at `wiki/overview.md` (General) and `wiki/overviews/<section-path>.md`, and are
LLM-owned like the rest of `wiki/` — don't hand-edit them.

### W14 — Solve problem sets with the Solver
The **Problem Set Solver** is a multi-turn chat (like ChatGPT) dedicated to one
course. Enable it by setting the course in `.llmwiki/config.toml` and relaunching:

```toml
solver_section = "academic/example-course"
```

A **Solver** entry then appears in the sidebar nav (it stays hidden while
`solver_section` is unset). Inside:

- **Sessions and model choice** — choose **GPT-5.6 Sol** or **Claude Fable 5**
  above **New session**. GPT is preselected when available; otherwise the first model
  with a configured key is selected. Unavailable models show the environment
  variable they need. The choice is locked for the new session; start another
  session to switch. Clicking a session resumes it, and **Delete** removes it
  (transcript and attached files). Sessions
  persist on disk under `.llmwiki/solver/` — they survive restarts, and every
  question in a session sees the whole conversation, so follow-ups can build on
  earlier answers ("now do part (c) using the same setup").
- **Ask a problem** — type the question and optionally attach the problem set as
  **PDFs or images** (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`; up to
  30 MB each). Attachments are sent **natively to the model** with your message —
  best fidelity for math notation and diagrams — and are **never ingested** into
  the wiki. They stay with the session and are automatically re-sent on follow-up
  turns.
- **Worked solutions** — unlike Ask (and unlike the example-course purpose's hints-only
  study boundary), the Solver gives **complete step-by-step solutions**: theorem
  hypotheses checked, course notation preserved, math rendered with KaTeX. Each
  turn retrieves fresh pages from the course wiki and cites them `[[slug]]`-style
  with the same **References** list and **ungrounded-citation warning** as Ask —
  if a cited page isn't in your wiki, you'll see the caution note.
- **Reasoning summaries** — both selectable models think at their highest effort.
  After a turn completes, any provider-generated summary appears collapsed above
  the worked solution. Expand it when useful. The app never streams or displays
  raw chain-of-thought, and a missing provider summary does not invalidate the
  solution.
- **Speed & cost** — solver turns run at **maximum reasoning effort**
  (`max` for both selectable models), so an answer can take a few minutes; the
  turn is bounded by `solver_request_timeout`. Fable has a **64,000-token combined
  thinking-and-answer cap**; GPT keeps the existing answer budget and reasoning
  reserve. Attachments are
  re-sent each turn, so very long sessions with big PDFs cost more — start a new
  session per problem set.
- **Customize it** — the solver's system prompt is the **solver** card in
  **Customize** (W12): override it for the course (e.g. "always verify with an
  alternative method") or edit the general default.

Set `OPENAI_API_KEY` for GPT and `ANTHROPIC_API_KEY` for Fable (set both to make
both choices available). OpenAI may require [organization
verification](https://developers.openai.com/api/docs/guides/reasoning#reasoning-summaries)
before it returns reasoning summaries. Claude Fable 5 requires [30-day data
retention and does not support Zero Data
Retention](https://platform.claude.com/docs/en/about-claude/models/overview); check
that policy before sending sensitive problem sets. A Fable refusal is reported as
an error and leaves the attempted turn and its new attachments unsaved; the app
never silently changes providers. These per-session choices do not change the
global provider used by Ask, Ingest, Lint, or overviews.

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
