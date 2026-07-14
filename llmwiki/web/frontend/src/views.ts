import { getJSON, postJSON, postForm, delJSON, escapeHtml } from "./api";
import { content, filterEl } from "./dom";
import {
  state,
  type IngestResult,
  type LintIssue,
  type Meta,
  type OverridesList,
  type PageRef,
  type QueryResult,
  type SectionOverrides,
} from "./state";
import { renderMarkdown, mount, animateIn, decorateWikilinks } from "./render";
import { renderSolver } from "./solver";
import { highlightSidebar, loadPages, renderPageList } from "./sidebar";
import { setBreadcrumb, setScopedBreadcrumb } from "./topbar";
import { renderLandingStats } from "./landing";
import { toast } from "./toast";
import { confirmDialog } from "./confirm-dialog";
import { setActiveScope } from "./scope-state";
import { setActiveNavigation } from "./workspace";
import {
  childSections,
  scopeNodes,
  sectionAncestors,
  sectionContains,
  sectionLabel,
  sectionPathLabel,
} from "./sections";

// The seeded root the UI relies on — not deletable (mirrors the backend guard).
const PROTECTED_SECTIONS = new Set(["academic"]);

export function setView(name: string): void {
  setActiveNavigation(name === "home" ? "workspace" : name);
  content.className = `content-view content-${name}`;
  highlightSidebar(null);
  if (name === "home") renderHome();
  else if (name === "ask") renderAsk();
  else if (name === "lint") renderLint();
  else if (name === "ingest") renderIngest();
  else if (name === "solver") void renderSolver("");
}

// Human-readable label for the current scope (drives Ask/Lint copy).
function scopeLabel(): string {
  return state.scope || "General — whole knowledge base";
}

// `accept` filter for file inputs, from the extensions the backend can ingest.
function acceptAttr(): string {
  return (state.meta.supported_exts || []).join(",");
}

// Provider behind the Ask answer, inferred from the configured key env var.
// Honest (reflects what's set up) without fabricating a specific model name.
function providerLabel(): string {
  const env = state.meta.api_key_env || "";
  if (/anthropic/i.test(env)) return "Anthropic";
  if (/openai/i.test(env)) return "OpenAI";
  return "";
}

async function renderHome(): Promise<void> {
  // Scope-aware: each section hub's "Browse overview" lands here with its scope,
  // so a course shows its own overview, a branch its branch overview, etc.
  setScopedBreadcrumb(state.scope, "Overview");
  mount('<p class="muted">Loading…</p>');
  try {
    const url = state.scope
      ? "/api/home?section=" + encodeURIComponent(state.scope)
      : "/api/home";
    const d = await getJSON<{ content: string }>(url);
    mount(
      renderMarkdown(
        d.content ||
          "_No overview here yet. Ingest a source into this section, or use **Regenerate overview** on the section hub._",
      ),
    );
  } catch (err) {
    mount(`<p class="notice">${escapeHtml((err as Error).message)}</p>`);
  }
}

export async function loadPage(slug: string): Promise<void> {
  setActiveNavigation("workspace");
  content.className = "content-view reader-view";
  highlightSidebar(slug);
  mount('<p class="muted">Loading…</p>');
  try {
    const p = await getJSON<PageRef & { content: string }>("/api/page/" + encodeURIComponent(slug));
    if (p.section !== state.scope) {
      setActiveScope(p.section); // scope follows the page you're reading
      filterEl.value = ""; // mirrors renderSection: a fresh scope starts unfiltered
      renderPageList(); // sidebar scope tree + page list reflect the new scope
      highlightSidebar(slug); // renderPageList rebuilt the anchors — re-highlight
    }
    setBreadcrumb(sectionAncestors(p.section), p.title); // also refreshes the scope chip
    const head =
      `<div class="page-head-row"><p class="eyebrow">${escapeHtml(p.type)}</p>` +
      `<button id="page-del" class="page-del" title="Delete this page" ` +
      `aria-label="Delete ${escapeHtml(p.title)}"><i class="ph ph-trash" aria-hidden="true"></i></button></div>` +
      `<h1>${escapeHtml(p.title)}</h1>`;
    mount(head + renderMarkdown(p.content));
    wirePageDelete(p);
  } catch (err) {
    mount(`<p class="notice">Could not load “${escapeHtml(slug)}”: ${escapeHtml((err as Error).message)}</p>`);
  }
}

// One-line orientation for a section hub.
function sectionDescription(scope: string): string {
  if (!scope)
    return "Your whole knowledge base — ask or lint across everything, or open a section below to focus.";
  if (scope === "academic")
    return "All your course knowledge. Each course below sees only its own material; ask or lint here to work across every course.";
  return "Everything filed under this section. The operations below are scoped to it and everything beneath it.";
}

// A section's own page: breadcrumb, scoped operations, child sections, and a form
// to scaffold a new child (a course under Academic, a sub-section elsewhere).
export function renderSection(scope: string): void {
  setActiveNavigation("workspace");
  content.className = "content-view scope-view";
  setActiveScope(scope);
  filterEl.value = ""; // a fresh scope starts with an unfiltered page list
  highlightSidebar(null);
  renderPageList(); // reflect the new scope in the sidebar tree + page list
  setBreadcrumb(sectionAncestors(scope)); // last node = the current section

  const isGeneral = scope === "";
  const isAcademic = scope === "academic";
  // Courses (and anything beneath them) are leaves under Academic — you can add
  // courses to Academic itself, but not sub-sections inside a course. General can
  // create top-level branches (siblings of Academic); the homepage offers the same.
  const canCreate = isGeneral || isAcademic || !sectionContains("academic", scope);
  const createLabel = isAcademic ? "New course" : isGeneral ? "New branch" : "New section";
  const headLabel = isGeneral ? "Branches" : isAcademic ? "Courses" : "Sub-sections";
  // Always surface the seeded `academic` branch under General, even before it
  // exists on disk (a fresh vault may not have filed anything yet).
  const children = isGeneral
    ? [...new Set([...PROTECTED_SECTIONS, ...childSections(scope, state.meta.sections)])].sort()
    : childSections(scope, state.meta.sections);
  const count = (node: string) =>
    state.pages.filter((p) => sectionContains(node, p.section)).length;

  const cards = children.length
    ? `<div class="hub-children">` +
      children
        .map((c) => {
          const n = count(c);
          const label = sectionLabel(c);
          const del = PROTECTED_SECTIONS.has(c)
            ? ""
            : `<button class="hub-card-del" data-section="${escapeHtml(c)}" ` +
              `aria-label="Delete ${escapeHtml(label)}" title="Delete"><i class="ph ph-trash" aria-hidden="true"></i></button>`;
          return (
            `<div class="hub-card">` +
            `<a class="hub-card-link" href="#/section/${c}">` +
            `<span class="hub-card-title">${escapeHtml(label)}</span>` +
            `<span class="hub-card-meta">${n} ${n === 1 ? "page" : "pages"}</span></a>` +
            del +
            `</div>`
          );
        })
        .join("") +
      `</div>`
    : "";

  // The children block carries the create control. When creation is disabled
  // (a course) we only show it if there are existing sub-sections to list.
  let childrenBlock = "";
  if (canCreate) {
    const empty = children.length
      ? ""
      : `<p class="muted hub-empty">No ${isAcademic ? "courses" : isGeneral ? "branches" : "sub-sections"} yet — create one to get started.</p>`;
    childrenBlock = `
    <div class="hub-head-row">
      <div class="hub-head">${headLabel}</div>
      <button id="new-section-btn" class="btn btn-primary btn-sm" type="button">+ ${createLabel}</button>
    </div>
    <form id="new-section-form" class="new-section-form" hidden>
      <input id="new-section-name" type="text" autocomplete="off"
        placeholder="${isAcademic ? "Course name" : isGeneral ? "Branch name" : "Section name"}…">
      <button type="submit" class="btn btn-primary">Create</button>
      <button type="button" id="new-section-cancel" class="btn">Cancel</button>
    </form>
    <div id="new-section-error"></div>
    ${cards}`;
  } else if (children.length) {
    childrenBlock = `
    <div class="hub-head-row"><div class="hub-head">${headLabel}</div></div>
    ${cards}`;
  }

  content.innerHTML = `
    <p class="eyebrow">${isGeneral ? "Knowledge base" : "Section"}</p>
    <h1>${escapeHtml(sectionLabel(scope))}</h1>
    <p class="hub-desc">${escapeHtml(sectionDescription(scope))}</p>
    <div class="hub-ops">
      <a class="btn" href="#/overview">Browse overview</a>
      <a class="btn" href="#/ask">Ask</a>
      <a class="btn" href="#/lint">Lint</a>
      <a class="btn" href="#/ingest">Ingest</a>
      <a class="btn" href="#/customize/${scope}">Customize</a>
      <button id="regen-overview-btn" class="btn" type="button" ${state.meta.has_api_key ? "" : "disabled"}
        title="${state.meta.has_api_key ? "Rewrite this section's overview with the model" : "Set an API key to regenerate overviews"}">Regenerate overview</button>
    </div>${childrenBlock}`;

  if (canCreate) wireCreateForm(scope);
  wireDeleteButtons(scope);
  wireRegenOverview(scope);
  animateIn();
}

// Wire the "Regenerate overview" button: ask the server to rewrite this section's
// overview with the model, then open the (now-refreshed) overview for this scope.
function wireRegenOverview(scope: string): void {
  const btn = document.getElementById("regen-overview-btn") as HTMLButtonElement | null;
  if (!btn || btn.disabled) return;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = "Regenerating…";
    try {
      await postJSON("/api/overview/refresh", { section: scope });
      toast("Overview regenerated");
      location.hash = "#/overview"; // show the refreshed overview for this scope
    } catch (err) {
      btn.disabled = false;
      btn.textContent = label;
      toast((err as Error).message);
    }
  });
}

// Wire the 🗑 button on each child card: confirm, delete on the server, then drop
// the section (and its pages/descendants) from local state and re-render the hub.
function wireDeleteButtons(scope: string): void {
  document.querySelectorAll<HTMLButtonElement>(".hub-card-del").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      const section = btn.dataset.section!;
      const label = sectionLabel(section);
      const confirmed = await confirmDialog({
        eyebrow: "Delete scope",
        title: `Delete ${label}?`,
        message: "Every concept, source, cache entry, override, and descendant in this scope will be permanently removed.",
        typedValue: label,
        confirmLabel: "Delete scope",
      });
      if (!confirmed) return;
      btn.disabled = true;
      try {
        await delJSON("/api/sections/" + section.split("/").map(encodeURIComponent).join("/"));
        state.meta.sections = state.meta.sections.filter((s) => !sectionContains(section, s));
        state.pages = state.pages.filter((p) => !sectionContains(section, p.section));
        renderPageList();
        renderSection(scope); // re-render this hub without the deleted card
      } catch (err) {
        btn.disabled = false;
        const errBox = document.getElementById("new-section-error");
        const msg = escapeHtml((err as Error).message);
        if (errBox) errBox.innerHTML = `<p class="notice">${msg}</p>`;
        else alert((err as Error).message);
      }
    });
  });
}

// Wire the 🗑 on the page reading view: confirm (the message spells out how far a
// source delete cascades), delete on the server, then refresh counts/sidebar and
// land on the page's section hub.
function wirePageDelete(p: PageRef): void {
  const btn = document.getElementById("page-del") as HTMLButtonElement | null;
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const msg =
      p.type === "source"
        ? `Delete source "${p.title}"? This also removes its raw and cached files, ` +
          `removes it from the provenance of concepts in this section, and deletes ` +
          `any concept left with no sources. This cannot be undone.`
        : `Delete concept "${p.title}"? The page and its search-index entries are ` +
          `removed. This cannot be undone.`;
    const confirmed = await confirmDialog({
      eyebrow: `Delete ${p.type}`,
      title: `Delete ${p.title}?`,
      message: msg,
      confirmLabel: `Delete ${p.type}`,
    });
    if (!confirmed) return;
    btn.disabled = true;
    try {
      const res = await delJSON<{ scrubbed: string[]; removed_concepts: string[] }>(
        `/api/page/${encodeURIComponent(p.slug)}?type=${encodeURIComponent(p.type)}` +
          `&section=${encodeURIComponent(p.section)}`,
      );
      try {
        state.meta = await getJSON<Meta>("/api/meta");
      } catch {
        /* keep current meta */
      }
      await loadPages(); // state.pages + state.slugSet + sidebar
      renderLandingStats();
      const n = res.removed_concepts.length;
      toast(
        `Deleted ${p.type} "${p.title}"` +
          (n ? ` — also deleted ${n} orphaned concept${n === 1 ? "" : "s"}` : ""),
      );
      location.hash = "#/section/" + p.section; // like wireRegenOverview's navigation
    } catch (err) {
      btn.disabled = false;
      toast((err as Error).message);
    }
  });
}

function wireCreateForm(scope: string): void {
  const form = document.getElementById("new-section-form") as HTMLFormElement;
  const nameInput = document.getElementById("new-section-name") as HTMLInputElement;
  const errBox = document.getElementById("new-section-error")!;
  const reset = () => {
    form.hidden = true;
    errBox.innerHTML = "";
    nameInput.value = "";
  };
  document.getElementById("new-section-btn")!.addEventListener("click", () => {
    form.hidden = !form.hidden;
    if (!form.hidden) nameInput.focus();
  });
  document.getElementById("new-section-cancel")!.addEventListener("click", reset);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    if (!name) return;
    errBox.innerHTML = "";
    try {
      const res = await postJSON<{ section: string; label: string }>(
        "/api/sections",
        { name, parent: scope },
      );
      if (!state.meta.sections.includes(res.section)) {
        state.meta.sections = [...state.meta.sections, res.section].sort();
      }
      renderPageList();
      location.hash = "#/section/" + res.section; // open the new section's page
    } catch (err) {
      errBox.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
    }
  });
}

// Example prompts shown as the Ask empty state — clicking one seeds the box.
const ASK_EXAMPLES = [
  "Summarize the key ideas across this section.",
  "How do these concepts connect to each other?",
  "What's a concrete example of this in practice?",
];

function renderAsk(): void {
  setScopedBreadcrumb(state.scope, "Ask");
  const dis = state.meta.has_api_key ? "" : "disabled";
  const examples = state.meta.has_api_key
    ? `<div class="ask-examples"><div class="ask-examples-head">Try asking</div>` +
      ASK_EXAMPLES.map(
        (q) => `<button type="button" class="ask-example" data-example="${escapeHtml(q)}">${escapeHtml(q)}</button>`,
      ).join("") +
      `</div>`
    : "";
  content.innerHTML = `
    <p class="eyebrow eyebrow-ai">Ask · grounded in your wiki</p>
    <h1>Ask</h1>
    ${state.meta.has_api_key ? "" : `<p class="notice">No API key found. Run <code>llmwiki set-key openai &lt;key&gt;</code> (or set <code>${escapeHtml(state.meta.api_key_env || "OPENAI_API_KEY")}</code>) and restart the server to ask questions.</p>`}
    <p class="page-meta">Answers are scoped to <strong>${escapeHtml(scopeLabel())}</strong> — change scope from the header.</p>
    <form id="ask-form">
      <textarea id="ask-q" placeholder="Ask a question answered from your wiki…" ${dis}></textarea>
      <div class="row ask-row">
        <label class="file-field">
          <span class="file-field-label">Attach files (optional)</span>
          <input id="ask-files" type="file" multiple accept="${escapeHtml(acceptAttr())}" ${dis}>
        </label>
        <button type="submit" class="btn btn-primary" ${dis}>Ask the model</button>
      </div>
    </form>
    <div id="answer">${examples}</div>`;
  document.getElementById("ask-form")!.addEventListener("submit", onAsk);
  document.querySelectorAll<HTMLButtonElement>(".ask-example").forEach((b) =>
    b.addEventListener("click", () => {
      const ta = document.getElementById("ask-q") as HTMLTextAreaElement;
      ta.value = b.dataset.example || "";
      ta.focus();
    }));
  animateIn();
}

// Grounding postscript shared by Ask and the Solver: the ungrounded-citations
// warning plus the numbered References list back to the pages an answer used.
export function answerExtrasHtml(pages_used?: string[], ungrounded?: string[]): string {
  let html = "";
  if (ungrounded && ungrounded.length) {
    // Grounding check: the answer cited pages that don't exist in the wiki, so
    // those claims aren't backed by provenance. Surface it rather than hide it.
    const names = ungrounded.map((s) => `<code>${escapeHtml(s)}</code>`).join(", ");
    html += `<p class="notice"><i class="ph ph-warning-circle" aria-hidden="true"></i> This answer cited ${ungrounded.length} page(s) not in your wiki: ${names}. Treat those claims with caution — they aren't grounded in a source.</p>`;
  }
  if (pages_used && pages_used.length) {
    // Numbered footnote-style references back to the pages the answer drew on.
    const items = pages_used
      .map((s) => `<li><a class="wikilink" data-nav="page:${escapeHtml(s)}">${escapeHtml(s)}</a></li>`)
      .join("");
    html += `<div class="answer-refs"><span class="eyebrow">References</span><ol class="ref-list">${items}</ol></div>`;
  }
  return html;
}

async function onAsk(e: Event): Promise<void> {
  e.preventDefault();
  const q = (document.getElementById("ask-q") as HTMLTextAreaElement).value.trim();
  if (!q) return;
  const filesEl = document.getElementById("ask-files") as HTMLInputElement | null;
  const files = filesEl?.files ? Array.from(filesEl.files) : [];
  const answerEl = document.getElementById("answer")!;
  answerEl.classList.remove("revealing");
  const msg = files.length ? "Reading your files and consulting your wiki…" : "Consulting your wiki…";
  answerEl.innerHTML = `<p class="ask-status"><span class="caret"></span>${msg}</p>`;
  try {
    const fd = new FormData();
    fd.append("question", q);
    if (state.scope) fd.append("section", state.scope);
    for (const f of files) fd.append("files", f);
    const res = await postForm<QueryResult>("/api/query", fd);
    let html = `<div class="answer-body">${renderMarkdown(res.answer)}</div>`;
    html += answerExtrasHtml(res.pages_used, res.ungrounded);
    const prov = providerLabel();
    html += `<p class="answer-by">Answered from your wiki${prov ? " · " + escapeHtml(prov) : ""}</p>`;
    answerEl.innerHTML = html;
    answerEl.classList.add("revealing"); // staggered "generated" reveal
    // decorate both rendered (wiki:) links and the reference links
    decorateWikilinks(answerEl);
  } catch (err) {
    answerEl.classList.remove("revealing");
    answerEl.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
  }
}

// Ingest view: upload files (or a URL) and compile them into the wiki. The form
// carries an explicit Destination picker — pre-set to `state.scope` (which
// follows the section hub or page you're in) and changeable before submitting —
// so new pages always land exactly where the form says they will.
function renderIngest(): void {
  setScopedBreadcrumb(state.scope, "Add source");
  paintIngest(content, false);
  animateIn();
}

export function renderIngestSheet(): void {
  const dialog = document.getElementById("source-sheet") as HTMLDialogElement;
  const body = document.getElementById("source-sheet-body")!;
  paintIngest(body, true);
  if (dialog.dataset.wired !== "true") {
    dialog.dataset.wired = "true";
    dialog.querySelector("[data-close-sheet]")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", () => {
      if (location.hash.replace(/^#/, "") === "/ingest") location.hash = "#/";
    });
  }
  if (!dialog.open) dialog.showModal();
}

function paintIngest(target: HTMLElement, sheet: boolean): void {
  const ok = state.meta.has_api_key;
  const dis = ok ? "" : "disabled";
  // Every selectable node: the General root, the seeded academic branch (even on
  // a fresh vault — mirrors renderSection), every known section + ancestors, and
  // the current scope (so preselection never misses).
  const nodes = scopeNodes([
    ...PROTECTED_SECTIONS,
    ...state.meta.sections,
    ...(state.scope ? [state.scope] : []),
  ]);
  const options = nodes
    .map(
      (n) =>
        `<option value="${escapeHtml(n)}"${n === state.scope ? " selected" : ""}>` +
        `${escapeHtml(sectionPathLabel(n))}</option>`,
    )
    .join("");
  target.innerHTML = `
    <div class="source-sheet-layout${sheet ? " is-sheet" : ""}">
      <header class="source-sheet-intro">
        <div class="source-icon"><i class="ph ph-upload-simple" aria-hidden="true"></i></div>
        <div><p class="eyebrow eyebrow-ai">Knowledge compilation</p><h1>Add source</h1>
        <p>Compile files or links into connected concepts inside this scope.</p></div>
      </header>
      ${ok ? "" : `<p class="notice source-key-notice">No API key found. Set <code>${escapeHtml(state.meta.api_key_env || "OPENAI_API_KEY")}</code> and restart the server to compile sources.</p>`}
      <form id="ingest-form" class="source-form">
        <section class="source-input-panel">
          <div class="source-tabs" role="tablist" aria-label="Source type">
            <button class="source-tab active" type="button" role="tab" aria-selected="true" data-source-mode="file">File</button>
            <button class="source-tab" type="button" role="tab" aria-selected="false" data-source-mode="url">URL</button>
          </div>
          <div class="source-mode-panel" data-source-panel="file">
            <label class="source-dropzone" for="ingest-files">
              <i class="ph ph-file-arrow-up" aria-hidden="true"></i>
              <strong>Drag &amp; drop files here</strong>
              <span>or <u>choose files</u></span>
              <input id="ingest-files" type="file" multiple accept="${escapeHtml(acceptAttr())}" ${dis}>
            </label>
            <div id="ingest-file-summary" class="selected-files muted">No files selected</div>
          </div>
          <div class="source-mode-panel" data-source-panel="url" hidden>
            <label>Source URL<input id="ingest-url" type="url" placeholder="https://…" autocomplete="off" ${dis}></label>
          </div>
          <label class="guidance-field">Compilation guidance <span>(optional)</span>
            <textarea id="ingest-prompt" placeholder="Focus on definitions and theorems; include examples and key proofs." ${dis}></textarea>
          </label>
        </section>
        <aside class="source-destination-panel">
          <label>Scope<select id="ingest-section" ${dis}>${options}</select></label>
          <p class="eyebrow">Destination</p>
          <strong>Compile into <span id="ingest-destination-label">${escapeHtml(sectionPathLabel(state.scope))}</span></strong>
          <p class="muted">New concept and source pages stay local to this knowledge base.</p>
          <button type="submit" class="button button-primary source-submit" ${dis}><i class="ph ph-sparkle" aria-hidden="true"></i><span>Compile into ${escapeHtml(sectionLabel(state.scope))}</span><i class="ph ph-arrow-right" aria-hidden="true"></i></button>
        </aside>
      </form>
      <div id="ingest-results" class="ingest-results"></div>
    </div>`;
  document.getElementById("ingest-form")!.addEventListener("submit", onIngest);
  wireIngestSurface();
}

function wireIngestSurface(): void {
  const files = document.getElementById("ingest-files") as HTMLInputElement;
  const summary = document.getElementById("ingest-file-summary")!;
  const destination = document.getElementById("ingest-section") as HTMLSelectElement;
  const destinationLabel = document.getElementById("ingest-destination-label")!;
  const submitText = document.querySelector<HTMLElement>(".source-submit span")!;
  const updateFiles = () => {
    const selected = files.files ? Array.from(files.files) : [];
    summary.innerHTML = selected.length
      ? selected.map((file) => `<span><i class="ph ph-file" aria-hidden="true"></i>${escapeHtml(file.name)}<small>${formatBytes(file.size)}</small></span>`).join("")
      : "No files selected";
  };
  files.addEventListener("change", updateFiles);
  const dropzone = document.querySelector<HTMLElement>(".source-dropzone");
  dropzone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
  dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));
  dropzone?.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
    if (event.dataTransfer?.files.length) {
      files.files = event.dataTransfer.files;
      updateFiles();
    }
  });
  document.querySelectorAll<HTMLButtonElement>("[data-source-mode]").forEach((tab) =>
    tab.addEventListener("click", () => {
      const mode = tab.dataset.sourceMode;
      document.querySelectorAll<HTMLButtonElement>("[data-source-mode]").forEach((candidate) => {
        const active = candidate === tab;
        candidate.classList.toggle("active", active);
        candidate.setAttribute("aria-selected", String(active));
      });
      document.querySelectorAll<HTMLElement>("[data-source-panel]").forEach((panel) =>
        panel.toggleAttribute("hidden", panel.dataset.sourcePanel !== mode));
    }));
  destination.addEventListener("change", () => {
    const label = sectionPathLabel(destination.value);
    destinationLabel.textContent = label;
    submitText.textContent = `Compile into ${sectionLabel(destination.value)}`;
  });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function onIngest(e: Event): Promise<void> {
  e.preventDefault();
  const filesEl = document.getElementById("ingest-files") as HTMLInputElement;
  const urlEl = document.getElementById("ingest-url") as HTMLInputElement;
  const promptEl = document.getElementById("ingest-prompt") as HTMLTextAreaElement | null;
  const out = document.getElementById("ingest-results")!;
  const files = filesEl.files ? Array.from(filesEl.files) : [];
  const url = urlEl.value.trim();
  // Optional guidance steering how every item in this submission is compiled.
  const prompt = promptEl?.value.trim() ?? "";
  // Every item carries the destination chosen on the form (pre-set to the
  // current scope), so the user always sees — and can correct — where the
  // compiled pages will land before submitting.
  const sectionEl = document.getElementById("ingest-section") as HTMLSelectElement | null;
  const section = sectionEl ? sectionEl.value : state.scope;
  const items: { label: string; fd: FormData }[] = [];
  for (const f of files) {
    const fd = new FormData();
    fd.append("file", f);
    fd.append("section", section);
    if (prompt) fd.append("prompt", prompt);
    items.push({ label: f.name, fd });
  }
  if (url) {
    const fd = new FormData();
    fd.append("url", url);
    fd.append("section", section);
    if (prompt) fd.append("prompt", prompt);
    items.push({ label: url, fd });
  }
  if (!items.length) {
    out.innerHTML = `<p class="notice">Choose at least one file or paste a URL.</p>`;
    return;
  }
  const btn = (e.target as HTMLFormElement).querySelector("button[type=submit]") as HTMLButtonElement;
  btn.disabled = true;
  // One row per item; filled in as each request completes (sequential — ingest
  // is slow and a parallel burst could overwhelm the model/server).
  out.innerHTML =
    `<div class="ingest-list">` +
    items
      .map(
        (it, i) =>
          `<div class="ingest-item" id="ingest-item-${i}">` +
          `<span class="ingest-item-status"><i class="ph ph-spinner-gap" aria-hidden="true"></i></span> ${escapeHtml(it.label)}</div>`,
      )
      .join("") +
    `</div>`;
  let anyOk = false;
  for (let i = 0; i < items.length; i++) {
    const row = document.getElementById(`ingest-item-${i}`)!;
    try {
      const res = await postForm<IngestResult>("/api/ingest", items[i].fd);
      anyOk = true;
      const n = res.concept_slugs.length;
      const warnings = res.warnings || [];
      const skipped = res.status === "skipped";
      const detail =
        skipped
          ? `skipped (${res.reason || "unchanged"})`
          : `${n} concept${n === 1 ? "" : "s"}`;
      const statusClass = warnings.length ? "warn" : skipped ? "skip" : "ok";
      const statusIcon = warnings.length ? "ph-warning-circle" : skipped ? "ph-info" : "ph-check-circle";
      const warningDetail = warnings.length
        ? ` · ${warnings.length} warning${warnings.length === 1 ? "" : "s"}: ${warnings.join(" ")}`
        : "";
      row.innerHTML =
        `<span class="ingest-item-status ${statusClass}"><i class="ph ${statusIcon}" aria-hidden="true"></i></span>` +
        `<span>${escapeHtml(res.title || items[i].label)} — ${escapeHtml(detail + warningDetail)}</span>` +
        (res.concept_slugs[0] ? ` <a href="#/page/${encodeURIComponent(res.concept_slugs[0])}">Open result <i class="ph ph-arrow-right" aria-hidden="true"></i></a>` : "");
    } catch (err) {
      row.innerHTML =
        `<span class="ingest-item-status err"><i class="ph ph-x-circle" aria-hidden="true"></i></span> ` +
        `${escapeHtml(items[i].label)} — ${escapeHtml((err as Error).message)}`;
    }
  }
  btn.disabled = false;
  if (anyOk) {
    // New pages exist now — refresh counts and the sidebar so they show up.
    try {
      state.meta = await getJSON<Meta>("/api/meta");
    } catch {
      /* keep current meta */
    }
    await loadPages();
    renderLandingStats(); // keep the landing counts live after an ingest
    filesEl.value = "";
    urlEl.value = "";
    if (promptEl) promptEl.value = "";
  }
}

function renderLint(): void {
  setScopedBreadcrumb(state.scope, "Review");
  const deepDis = state.meta.has_api_key ? "" : "disabled";
  content.innerHTML = `
    <p class="eyebrow">Editorial review</p>
    <h1>Review</h1>
    <p class="page-meta">Checks are scoped to <strong>${escapeHtml(scopeLabel())}</strong> — change scope from the header.</p>
    <div class="row">
      <button id="lint-run" class="btn btn-primary">Run checks</button>
      <label><input type="checkbox" id="lint-deep" ${deepDis}> deep review (uses API)</label>
    </div>
    <div id="lint-results"></div>`;
  document.getElementById("lint-run")!.addEventListener("click", runLint);
  animateIn();
}

async function runLint(): Promise<void> {
  const deep = (document.getElementById("lint-deep") as HTMLInputElement).checked;
  const out = document.getElementById("lint-results")!;
  out.innerHTML = '<p class="ask-status"><span class="caret"></span>Reviewing…</p>';
  const scopeParam = state.scope ? "&section=" + encodeURIComponent(state.scope) : "";
  try {
    const issues = await getJSON<LintIssue[]>("/api/lint?deep=" + (deep ? "true" : "false") + scopeParam);
    if (!issues.length) {
      out.innerHTML = '<p class="lint-clean"><i class="ph ph-check-circle" aria-hidden="true"></i> Clean — no errata in this scope.</p>';
      return;
    }
    out.innerHTML = issues
      .map(
        (i) =>
          `<div class="lint-issue"><span class="lint-level ${escapeHtml(i.level)}">${escapeHtml(i.level)}</span>` +
          `<span><a class="lint-page" data-nav="page:${escapeHtml(i.page)}">${escapeHtml(i.page)}</a> — ${escapeHtml(i.message)}</span></div>`,
      )
      .join("");
  } catch (err) {
    out.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
  }
}

// ── Customize ──────────────────────────────────────────────────────────────
// Per-branch override of the LLM instruction set. Each component is the
// operation prompt (ingest/answer/lint) or the purpose/schema; a branch either
// carries its own override or inherits the general default. One Save can fan out
// to several branches that are still on the general default (the targets panel).

const CUST_COMPONENTS: { key: string; label: string; help: string }[] = [
  { key: "purpose", label: "Purpose", help: "This branch's goals and scope — what its knowledge base is for." },
  { key: "schema", label: "Schema", help: "Page format the compiler must follow: frontmatter and body sections." },
  { key: "ingest_analysis", label: "Ingest · analysis", help: "How a new source is read to decide which concepts it covers." },
  { key: "ingest_generation", label: "Ingest · generation", help: "How concept and source pages are written from a source." },
  { key: "answer", label: "Answer · Ask", help: "How questions are answered from your wiki pages." },
  { key: "solve", label: "Solver · problem sets", help: "How the Problem Set Solver works problems: full solutions grounded in this branch's pages." },
  { key: "lint", label: "Lint · deep review", help: "What the deep editorial review looks for." },
];

export async function renderCustomize(section: string): Promise<void> {
  setActiveScope(section);
  setActiveNavigation("workspace");
  content.className = "content-view settings-view";
  highlightSidebar(null);
  renderPageList();
  setScopedBreadcrumb(section, "Scope settings");
  content.innerHTML = '<p class="muted">Loading…</p>';
  try {
    const list = await getJSON<OverridesList>("/api/overrides");
    // The General root ("") has no per-section file: it *is* the baseline, built
    // here from the list endpoint's general texts.
    const detail: SectionOverrides =
      section === ""
        ? {
            section: "",
            label: "General",
            components: Object.fromEntries(
              list.components.map((c) => [c, { effective: list.general[c], override: null, general: list.general[c] }]),
            ),
          }
        : await getJSON<SectionOverrides>(
            "/api/overrides/" + section.split("/").map(encodeURIComponent).join("/"),
          );
    paintCustomize(section, detail, list);
  } catch (err) {
    content.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
  }
}

function customizeTargets(section: string, list: OverridesList): string {
  if (section === "") return "";
  const others = list.sections.filter((s) => s.section !== section);
  if (!others.length) return "";
  const rows = others
    .map((s) => {
      const n = Object.values(s.status).filter((v) => v === "override").length;
      const hint = n ? `${n} overridden` : "on general default";
      return (
        `<label class="cust-target"><input type="checkbox" class="cust-target-cb" value="${escapeHtml(s.section)}">` +
        `<span class="cust-target-name">${escapeHtml(s.label)}</span>` +
        `<span class="cust-target-hint">${hint}</span></label>`
      );
    })
    .join("");
  return `
    <div class="cust-targets">
      <div class="cust-targets-head">Also apply each Save to</div>
      <p class="cust-targets-hint muted">Pick other branches to receive the same change when you Save a card. Leave all unchecked to change only this branch.</p>
      <div class="cust-target-list">${rows}</div>
    </div>`;
}

function customizeCard(comp: { key: string; label: string; help: string }, st: { effective: string; override: string | null }, isGeneral: boolean): string {
  const overridden = st.override !== null;
  const badge = isGeneral
    ? `<span class="cust-badge baseline">Baseline</span>`
    : `<span class="cust-badge ${overridden ? "override" : "inherited"}">${overridden ? "Override" : "Inherited"}</span>`;
  const reset = isGeneral
    ? ""
    : `<button type="button" class="btn btn-sm cust-reset" data-key="${comp.key}" ${overridden ? "" : "disabled"}>Reset to general</button>`;
  return `
    <section class="cust-card" data-key="${comp.key}">
      <div class="cust-card-head">
        <div class="cust-card-title">${escapeHtml(comp.label)}</div>
        ${badge}
      </div>
      <p class="cust-card-help">${escapeHtml(comp.help)}</p>
      <textarea class="cust-editor" data-key="${comp.key}" spellcheck="false" rows="9">${escapeHtml(st.effective)}</textarea>
      <div class="cust-card-actions">
        <button type="button" class="btn btn-primary btn-sm cust-save" data-key="${comp.key}">Save</button>
        <button type="button" class="btn btn-sm cust-undo" data-key="${comp.key}" disabled>Undo</button>
        <button type="button" class="btn btn-sm cust-copy" data-key="${comp.key}">Copy</button>
        ${reset}
        <span class="cust-card-msg" data-key="${comp.key}"></span>
      </div>
    </section>`;
}

function paintCustomize(section: string, detail: SectionOverrides, list: OverridesList): void {
  const isGeneral = section === "";
  const label = isGeneral ? "General" : sectionLabel(section);
  const cards = CUST_COMPONENTS.map((c) =>
    customizeCard(c, detail.components[c.key], isGeneral),
  ).join("");
  content.innerHTML = `
    <p class="eyebrow eyebrow-ai">Scope settings · LLM instructions</p>
    <h1>${escapeHtml(label)}</h1>
    <p class="page-meta">${
      isGeneral
        ? "The shared default every branch inherits."
        : `How the model ingests, answers, and lints in <strong>${escapeHtml(label)}</strong>. Each card overrides the general default for this branch only.`
    }</p>
    ${isGeneral ? `<p class="notice">You're editing the <strong>general baseline</strong>. Changes here apply to every branch that hasn't set its own override.</p>` : ""}
    ${customizeTargets(section, list)}
    <div class="cust-cards">${cards}</div>`;
  wireCustomize(section, detail);
  animateIn();
}

function wireCustomize(section: string, detail: SectionOverrides): void {
  const checkedTargets = () =>
    Array.from(document.querySelectorAll<HTMLInputElement>(".cust-target-cb:checked")).map((cb) => cb.value);
  const setMsg = (key: string, text: string, cls = "muted") => {
    const el = document.querySelector(`.cust-card-msg[data-key="${key}"]`);
    if (el) el.innerHTML = text ? `<span class="${cls}">${escapeHtml(text)}</span>` : "";
  };

  // Last-saved text per component — what "Undo current changes" reverts to (the
  // text loaded into the editor, refreshed on every successful Save/Reset). This
  // is unsaved-edit undo, distinct from "Reset to general" (which drops the
  // override entirely).
  const editor = (key: string) =>
    document.querySelector<HTMLTextAreaElement>(`textarea.cust-editor[data-key="${key}"]`)!;
  const saved: Record<string, string> = {};
  CUST_COMPONENTS.forEach((c) => (saved[c.key] = detail.components[c.key].effective));
  const refreshUndo = (key: string) => {
    const btn = document.querySelector<HTMLButtonElement>(`.cust-undo[data-key="${key}"]`);
    if (btn) btn.disabled = editor(key).value === saved[key];
  };

  // Enable Undo only while an editor has unsaved changes.
  document.querySelectorAll<HTMLTextAreaElement>("textarea.cust-editor").forEach((ta) =>
    ta.addEventListener("input", () => refreshUndo(ta.dataset.key!)),
  );

  document.querySelectorAll<HTMLButtonElement>(".cust-undo").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.key!;
      editor(key).value = saved[key];
      refreshUndo(key);
      toast("Reverted unsaved changes");
    });
  });

  document.querySelectorAll<HTMLButtonElement>(".cust-copy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.dataset.key!;
      try {
        await navigator.clipboard.writeText(editor(key).value);
        toast("Copied to clipboard");
      } catch {
        setMsg(key, "Couldn't copy — clipboard blocked.", "cust-err");
      }
    });
  });
  const markStatus = (key: string, overridden: boolean) => {
    const card = document.querySelector(`.cust-card[data-key="${key}"]`);
    const badge = card?.querySelector(".cust-badge");
    if (badge && !badge.classList.contains("baseline")) {
      badge.className = "cust-badge " + (overridden ? "override" : "inherited");
      badge.textContent = overridden ? "Override" : "Inherited";
    }
    const reset = card?.querySelector<HTMLButtonElement>(".cust-reset");
    if (reset) reset.disabled = !overridden;
  };

  document.querySelectorAll<HTMLButtonElement>(".cust-save").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.dataset.key!;
      const ta = document.querySelector<HTMLTextAreaElement>(`textarea.cust-editor[data-key="${key}"]`)!;
      const sections = [section, ...checkedTargets()];
      btn.disabled = true;
      setMsg(key, "Saving…");
      try {
        await postJSON("/api/overrides", { sections, set: { [key]: ta.value } });
        markStatus(key, true);
        saved[key] = ta.value; // new last-saved baseline for Undo
        refreshUndo(key);
        setMsg(key, "");
        toast(sections.length > 1 ? `Saved — applied to ${sections.length} branches` : "Saved");
      } catch (err) {
        setMsg(key, (err as Error).message, "cust-err");
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll<HTMLButtonElement>(".cust-reset").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.dataset.key!;
      btn.disabled = true;
      try {
        await postJSON("/api/overrides", { sections: [section], reset: [key] });
        const ta = document.querySelector<HTMLTextAreaElement>(`textarea.cust-editor[data-key="${key}"]`)!;
        ta.value = detail.components[key].general; // show the inherited text
        markStatus(key, false);
        saved[key] = detail.components[key].general; // Undo baseline follows the reset
        refreshUndo(key);
        toast("Reset to general default");
      } catch (err) {
        btn.disabled = false;
        setMsg(key, (err as Error).message, "cust-err");
      }
    });
  });
}
