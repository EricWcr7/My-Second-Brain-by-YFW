import { getJSON, postJSON, escapeHtml } from "./api";
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
    const href = node ? "#/section/" + node : "#/";
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
      `<h1>${escapeHtml(p.title)}</h1>` +
      `<p class="page-meta">${escapeHtml(p.type)}</p>`;
    mount(head + renderMarkdown(p.content));
  } catch (err) {
    mount(`<p class="notice">Could not load “${escapeHtml(slug)}”: ${escapeHtml((err as Error).message)}</p>`);
  }
}

// One-line orientation for a section hub.
function sectionDescription(scope: string): string {
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

  const isAcademic = scope === "academic";
  // Courses (and anything beneath them) are leaves under Academic — you can add
  // courses to Academic itself, but not sub-sections inside a course.
  const canCreate = isAcademic || !sectionContains("academic", scope);
  const createLabel = isAcademic ? "New course" : "New section";
  const headLabel = isAcademic ? "Courses" : "Sub-sections";
  const children = childSections(scope, state.meta.sections);
  const count = (node: string) =>
    state.pages.filter((p) => sectionContains(node, p.section)).length;

  const cards = children.length
    ? `<div class="hub-children">` +
      children
        .map((c) => {
          const n = count(c);
          return (
            `<a class="hub-card" href="#/section/${c}">` +
            `<span class="hub-card-title">${escapeHtml(sectionLabel(c))}</span>` +
            `<span class="hub-card-meta">${n} ${n === 1 ? "page" : "pages"}</span></a>`
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
    <h1>${escapeHtml(sectionLabel(scope))}</h1>
    <p class="hub-desc">${escapeHtml(sectionDescription(scope))}</p>
    <div class="hub-ops">
      <a class="btn" href="#/overview">Browse overview</a>
      <a class="btn" href="#/ask">Ask</a>
      <a class="btn" href="#/lint">Lint</a>
    </div>${childrenBlock}`;

  if (canCreate) wireCreateForm(scope);
  animateIn();
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

function renderAsk(): void {
  const dis = state.meta.has_api_key ? "" : "disabled";
  content.innerHTML = `
    ${crumbs(state.scope, { leafLink: true })}
    <h1>Ask</h1>
    ${state.meta.has_api_key ? "" : `<p class="notice">Set <code>${escapeHtml(state.meta.api_key_env || "OPENAI_API_KEY")}</code> and restart the server to ask questions.</p>`}
    <p class="page-meta">Answers are scoped to <strong>${escapeHtml(scopeLabel())}</strong> — switch sections in the sidebar.</p>
    <form id="ask-form">
      <textarea id="ask-q" placeholder="Ask a question answered from your wiki…" ${dis}></textarea>
      <div class="row">
        <button type="submit" class="btn btn-primary" ${dis}>Ask</button>
      </div>
    </form>
    <div id="answer"></div>`;
  document.getElementById("ask-form")!.addEventListener("submit", onAsk);
  animateIn();
}

async function onAsk(e: Event): Promise<void> {
  e.preventDefault();
  const q = (document.getElementById("ask-q") as HTMLTextAreaElement).value.trim();
  if (!q) return;
  const section = state.scope || null;
  const answerEl = document.getElementById("answer")!;
  answerEl.innerHTML = '<p><span class="spinner"></span> Thinking… (the model can take a while)</p>';
  try {
    const res = await postJSON<QueryResult>("/api/query", { question: q, section });
    let html = renderMarkdown(res.answer);
    if (res.pages_used && res.pages_used.length) {
      const links = res.pages_used
        .map((s) => `<a class="wikilink" data-slug="${escapeHtml(s)}">${escapeHtml(s)}</a>`)
        .join(", ");
      html += `<div class="pages-used">Pages used: ${links}</div>`;
    }
    answerEl.innerHTML = html;
    // decorate both rendered (wiki:) links and the manual pages-used links
    decorateWikilinks(answerEl);
  } catch (err) {
    answerEl.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
  }
}

function renderLint(): void {
  const deepDis = state.meta.has_api_key ? "" : "disabled";
  content.innerHTML = `
    ${crumbs(state.scope, { leafLink: true })}
    <h1>Lint</h1>
    <p class="page-meta">Checks are scoped to <strong>${escapeHtml(scopeLabel())}</strong> — switch sections in the sidebar.</p>
    <div class="row">
      <button id="lint-run" class="btn btn-primary">Run checks</button>
      <label><input type="checkbox" id="lint-deep" ${deepDis}> deep review (uses API)</label>
    </div>
    <div id="lint-results" style="margin-top:20px"></div>`;
  document.getElementById("lint-run")!.addEventListener("click", runLint);
  animateIn();
}

async function runLint(): Promise<void> {
  const deep = (document.getElementById("lint-deep") as HTMLInputElement).checked;
  const out = document.getElementById("lint-results")!;
  out.innerHTML = '<p><span class="spinner"></span> Running…</p>';
  const scopeParam = state.scope ? "&section=" + encodeURIComponent(state.scope) : "";
  try {
    const issues = await getJSON<LintIssue[]>("/api/lint?deep=" + (deep ? "true" : "false") + scopeParam);
    if (!issues.length) {
      out.innerHTML = '<p class="muted">No issues found. ✓</p>';
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
