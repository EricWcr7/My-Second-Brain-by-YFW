import { getJSON, postJSON, delJSON, escapeHtml } from "./api";
import { content } from "./dom";
import { state, type LintIssue, type PageRef, type QueryResult } from "./state";
import { renderMarkdown, mount, animateIn, decorateWikilinks } from "./render";
import { highlightSidebar, renderPageList } from "./sidebar";
import {
  childSections,
  sectionAncestors,
  sectionContains,
  sectionLabel,
} from "./sections";

// The seeded roots the UI relies on — not deletable (mirrors the backend guard).
const PROTECTED_SECTIONS = new Set(["academic", "non-academic"]);

export function setView(name: string): void {
  document.querySelectorAll<HTMLButtonElement>("#nav button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  highlightSidebar(null);
  if (name === "home") renderHome();
  else if (name === "ask") renderAsk();
  else if (name === "lint") renderLint();
}

// Human-readable label for the current scope (drives Ask/Lint copy).
function scopeLabel(): string {
  return state.scope || "General — whole knowledge base";
}

// Provider behind the Ask answer, inferred from the configured key env var.
// Honest (reflects what's set up) without fabricating a specific model name.
function providerLabel(): string {
  const env = state.meta.api_key_env || "";
  if (/anthropic/i.test(env)) return "Anthropic";
  if (/openai/i.test(env)) return "OpenAI";
  return "";
}

// Hierarchy breadcrumb (General › Academic › …). Each ancestor links to its page
// — "" is General (the landing), any other node is its `#/section/<path>` hub.
// `leafLink` keeps the last crumb clickable (used when the leaf isn't the section
// itself, e.g. on a page or Ask/Lint); the hub renders its own leaf as current.
function crumbs(scope: string, opts: { leafLink?: boolean } = {}): string {
  const chain = sectionAncestors(scope);
  const parts = chain.map((node, i) => {
    const last = i === chain.length - 1;
    const label = escapeHtml(sectionLabel(node));
    if (last && !opts.leafLink) return `<span class="crumb-current">${label}</span>`;
    const href = "#/section/" + node; // node "" -> the General hub
    return `<a class="crumb" href="${href}">${label}</a>`;
  });
  return `<nav class="crumbs">${parts.join('<span class="crumb-sep">›</span>')}</nav>`;
}

async function renderHome(): Promise<void> {
  mount('<p class="muted">Loading…</p>');
  try {
    const d = await getJSON<{ content: string }>("/api/home");
    mount(renderMarkdown(d.content || "_No overview yet. Ingest a source from the CLI._"));
  } catch (err) {
    mount(`<p class="notice">${escapeHtml((err as Error).message)}</p>`);
  }
}

export async function loadPage(slug: string): Promise<void> {
  document.querySelectorAll<HTMLButtonElement>("#nav button").forEach((b) =>
    b.classList.remove("active"));
  highlightSidebar(slug);
  mount('<p class="muted">Loading…</p>');
  try {
    const p = await getJSON<PageRef & { content: string }>("/api/page/" + encodeURIComponent(slug));
    const head =
      crumbs(p.section, { leafLink: true }) +
      `<p class="eyebrow">${escapeHtml(p.type)}</p>` +
      `<h1>${escapeHtml(p.title)}</h1>`;
    mount(head + renderMarkdown(p.content));
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
  if (scope === "non-academic")
    return "Personal, free-form knowledge — notes and references that don't belong to a course.";
  return "Everything filed under this section. The operations below are scoped to it and everything beneath it.";
}

// A section's own page: breadcrumb, scoped operations, child sections, and a form
// to scaffold a new child (a course under Academic, a sub-section elsewhere).
export function renderSection(scope: string): void {
  document.querySelectorAll<HTMLButtonElement>("#nav button").forEach((b) =>
    b.classList.remove("active"));
  state.scope = scope;
  highlightSidebar(null);
  renderPageList(); // reflect the new scope in the sidebar tree + page list

  const isGeneral = scope === "";
  const isAcademic = scope === "academic";
  // Courses (and anything beneath them) are leaves under Academic — you can add
  // courses to Academic itself, but not sub-sections inside a course. General's
  // children are the fixed seeded branches, so it offers no create control.
  const canCreate = !isGeneral && (isAcademic || !sectionContains("academic", scope));
  const createLabel = isAcademic ? "New course" : "New section";
  const headLabel = isGeneral ? "Sections" : isAcademic ? "Courses" : "Sub-sections";
  // Always surface the seeded branches under General, even before either exists
  // on disk (a fresh vault may have only `academic/`).
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
              `aria-label="Delete ${escapeHtml(label)}" title="Delete">🗑</button>`;
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
      : `<p class="muted hub-empty">No ${isAcademic ? "courses" : "sub-sections"} yet — create one to get started.</p>`;
    childrenBlock = `
    <div class="hub-head-row">
      <div class="hub-head">${headLabel}</div>
      <button id="new-section-btn" class="btn btn-primary btn-sm" type="button">+ ${createLabel}</button>
    </div>
    <form id="new-section-form" class="new-section-form" hidden>
      <input id="new-section-name" type="text" autocomplete="off"
        placeholder="${isAcademic ? "Course name" : "Section name"}…">
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
    ${crumbs(scope)}
    <p class="eyebrow">${isGeneral ? "Knowledge base" : "Section"}</p>
    <h1>${escapeHtml(sectionLabel(scope))}</h1>
    <p class="hub-desc">${escapeHtml(sectionDescription(scope))}</p>
    <div class="hub-ops">
      <a class="btn" href="#/overview">Browse overview</a>
      <a class="btn" href="#/ask">Ask</a>
      <a class="btn" href="#/lint">Lint</a>
    </div>${childrenBlock}`;

  if (canCreate) wireCreateForm(scope);
  wireDeleteButtons(scope);
  animateIn();
}

// Wire the 🗑 button on each child card: confirm, delete on the server, then drop
// the section (and its pages/descendants) from local state and re-render the hub.
function wireDeleteButtons(scope: string): void {
  document.querySelectorAll<HTMLButtonElement>(".hub-card-del").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      const section = btn.dataset.section!;
      const label = sectionLabel(section);
      if (!confirm(`Delete "${label}" and all its concept and source files? This cannot be undone.`))
        return;
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
  const dis = state.meta.has_api_key ? "" : "disabled";
  const examples = state.meta.has_api_key
    ? `<div class="ask-examples"><div class="ask-examples-head">Try asking</div>` +
      ASK_EXAMPLES.map(
        (q) => `<button type="button" class="ask-example" data-example="${escapeHtml(q)}">${escapeHtml(q)}</button>`,
      ).join("") +
      `</div>`
    : "";
  content.innerHTML = `
    ${crumbs(state.scope, { leafLink: true })}
    <p class="eyebrow eyebrow-ai">Ask · grounded in your wiki</p>
    <h1>Ask</h1>
    ${state.meta.has_api_key ? "" : `<p class="notice">No API key found. Run <code>llmwiki set-key openai &lt;key&gt;</code> (or set <code>${escapeHtml(state.meta.api_key_env || "OPENAI_API_KEY")}</code>) and restart the server to ask questions.</p>`}
    <p class="page-meta">Answers are scoped to <strong>${escapeHtml(scopeLabel())}</strong> — switch sections in the sidebar.</p>
    <form id="ask-form">
      <textarea id="ask-q" placeholder="Ask a question answered from your wiki…" ${dis}></textarea>
      <div class="row">
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

async function onAsk(e: Event): Promise<void> {
  e.preventDefault();
  const q = (document.getElementById("ask-q") as HTMLTextAreaElement).value.trim();
  if (!q) return;
  const section = state.scope || null;
  const answerEl = document.getElementById("answer")!;
  answerEl.classList.remove("revealing");
  answerEl.innerHTML = '<p class="ask-status"><span class="caret"></span>Consulting your wiki…</p>';
  try {
    const res = await postJSON<QueryResult>("/api/query", { question: q, section });
    let html = `<div class="answer-body">${renderMarkdown(res.answer)}</div>`;
    if (res.pages_used && res.pages_used.length) {
      // Numbered footnote-style references back to the pages the answer drew on.
      const items = res.pages_used
        .map((s) => `<li><a class="wikilink" data-slug="${escapeHtml(s)}">${escapeHtml(s)}</a></li>`)
        .join("");
      html += `<div class="answer-refs"><span class="eyebrow">References</span><ol class="ref-list">${items}</ol></div>`;
    }
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

function renderLint(): void {
  const deepDis = state.meta.has_api_key ? "" : "disabled";
  content.innerHTML = `
    ${crumbs(state.scope, { leafLink: true })}
    <p class="eyebrow">Editorial review</p>
    <h1>Lint</h1>
    <p class="page-meta">Checks are scoped to <strong>${escapeHtml(scopeLabel())}</strong> — switch sections in the sidebar.</p>
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
      out.innerHTML = '<p class="lint-clean">✓ Clean — no errata in this scope.</p>';
      return;
    }
    out.innerHTML = issues
      .map(
        (i) =>
          `<div class="lint-issue"><span class="lint-level ${escapeHtml(i.level)}">${escapeHtml(i.level)}</span>` +
          `<span><span class="lint-page" data-slug="${escapeHtml(i.page)}">${escapeHtml(i.page)}</span> — ${escapeHtml(i.message)}</span></div>`,
      )
      .join("");
  } catch (err) {
    out.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
  }
}
