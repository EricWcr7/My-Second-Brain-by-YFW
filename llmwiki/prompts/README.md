# Prompt catalog

The system prompts that drive every LLM call live here as plain `.md` files,
loaded by `prompts.load("<name>.md")` ([`__init__.py`](__init__.py)) and passed as
the `system` argument to a provider method. Keeping them in-repo (not inline in
code) makes them inspectable, diff-able, and eval-able — the discoverability the
`llm-engineering` rule asks for.

These `.md` files are the **general defaults**. Each call resolves its system
prompt **per section** through [`overrides.py`](../overrides.py): if the section
being operated on has an override (`.llmwiki/sections/<section>/<component>.md`) it
replaces the default; otherwise the packaged prompt here is used. The vault's
`wiki/purpose.md` + `wiki/schema.md` are appended the same way and are overridable
per section too (`lint` is fed purpose but not schema). Structured-output prompts
return a **Pydantic** model (validated by `provider.parse`), so a malformed
response raises rather than corrupting the wiki.

| Prompt | Used by | Provider call | Output shape |
| --- | --- | --- | --- |
| `answer.md` | [`query.py`](../query.py) | `complete` | free-form Markdown |
| `ingest_analysis.md` | [`ingest.py`](../ingest.py) pass 1 | `parse` | `SourceAnalysis` |
| `ingest_generation.md` | [`ingest.py`](../ingest.py) pass 2 | `parse` | `GenerationResult` |
| `lint.md` | [`lint.py`](../lint.py) `--deep` | `parse` | `LintFindings` |

---

## `answer.md`
- **Purpose:** answer a question using **only** the retrieved wiki pages, with
  inline `[[slug]]` citations and a closing Sources list.
- **Inputs:** the question + a token-budgeted set of retrieved concept-page bodies
  (and any transient file attachments) as the `user` message; `purpose.md` +
  `schema.md` + an optional format directive (prose/table/slides) as system.
- **Output shape:** Markdown prose (or a comparison table / Marp deck). No schema.
- **Refusal/failure behavior:** if the pages don't cover the question it must say so
  plainly and point to the nearest pages — **not** invent facts or citations.
- **Eval method:** `tests/eval/test_grounding.py` (`make eval`) — the grounding
  check (`query.answer`) flags any `[[slug]]` that resolves to no wiki page.
- **Known failure modes:** inventing a `[[slug]]` (caught + surfaced as
  `ungrounded`); citing a real page it wasn't shown; over-summarizing the
  material (the prompt pushes for fidelity, preserving math/code/quotations as
  written).

## `ingest_analysis.md`
- **Purpose:** pass 1 of ingest — decide which **concepts** a new source covers, a
  short summary, and contradictions with existing pages.
- **Inputs:** the normalized source Markdown + the list of existing concept titles
  in the target section; `purpose.md` + `schema.md` as system.
- **Output shape:** `SourceAnalysis` (see [`ingest.py`](../ingest.py)).
- **Refusal/failure behavior:** must not invent concepts the source doesn't cover;
  reuses existing titles verbatim to avoid near-duplicates.
- **Eval method:** `tests/test_ingest.py` with a faked provider (golden analysis).
- **Known failure modes:** over-splitting into trivial concepts; near-duplicate
  titles when the existing-titles list is incomplete.

## `ingest_generation.md`
- **Purpose:** pass 2 of ingest — write/merge the concept pages and the source page
  per the wiki schema, preserving math and detail.
- **Inputs:** source text + the pass-1 analysis + existing page bodies to merge +
  the concept index for linking; `purpose.md` + `schema.md` as system.
- **Output shape:** `GenerationResult` (concept + source page drafts; see
  [`ingest.py`](../ingest.py)).
- **Refusal/failure behavior:** only links `[[slug]]` to concepts in the provided
  index or created in the same response; merges rather than dropping existing detail.
- **Eval method:** `tests/test_ingest.py` (faked generation; asserts pages written,
  provenance merged).
- **Known failure modes:** flattening technical substance into summary; dangling
  wikilinks to not-yet-created concepts (structural `lint` flags these).

## `lint.md`
- **Purpose:** the deep (LLM) lint pass — surface contradictions, missing concepts,
  stale/unclear claims, plus growth suggestions (missing cross-refs, questions,
  sources to seek, data gaps).
- **Inputs:** the index + a sample of page contents; `purpose.md` (no schema).
- **Output shape:** `LintFindings` (see [`lint.py`](../lint.py)).
- **Refusal/failure behavior:** returns empty lists where there's nothing to report;
  *names* data gaps but performs **no** web search (suggestions only).
- **Eval method:** `tests/test_lint.py` (faked findings) + the deterministic
  structural checks that run offline alongside it.
- **Known failure modes:** speculative suggestions on a thin wiki; flagging
  intentional redundancy as contradiction.
