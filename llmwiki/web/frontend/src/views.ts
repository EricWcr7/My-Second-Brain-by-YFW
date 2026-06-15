import { getJSON, postJSON, escapeHtml } from "./api";
import { content } from "./dom";
import { state, type LintIssue, type PageRef, type QueryResult } from "./state";
import { renderMarkdown, mount, animateIn, decorateWikilinks } from "./render";
import { highlightSidebar } from "./sidebar";

export function setView(name: string): void {
  document.querySelectorAll<HTMLButtonElement>("#nav button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  highlightSidebar(null);
  if (name === "home") renderHome();
  else if (name === "ask") renderAsk();
  else if (name === "lint") renderLint();
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
      `<h1>${escapeHtml(p.title)}</h1>` +
      `<p class="muted">${escapeHtml(p.type)} · ${escapeHtml(p.course)}</p>`;
    mount(head + renderMarkdown(p.content));
  } catch (err) {
    mount(`<p class="notice">Could not load “${escapeHtml(slug)}”: ${escapeHtml((err as Error).message)}</p>`);
  }
}

function renderAsk(): void {
  const dis = state.meta.has_api_key ? "" : "disabled";
  const courseOpts = ['<option value="">All courses</option>']
    .concat(state.meta.courses.map((c) => `<option>${escapeHtml(c)}</option>`))
    .join("");
  content.innerHTML = `
    <h1>Ask</h1>
    ${state.meta.has_api_key ? "" : `<p class="notice">Set <code>${escapeHtml(state.meta.api_key_env || "OPENAI_API_KEY")}</code> and restart the server to ask questions.</p>`}
    <form id="ask-form">
      <textarea id="ask-q" placeholder="Ask a question answered from your wiki…" ${dis}></textarea>
      <div class="row">
        <select id="ask-course" ${dis}>${courseOpts}</select>
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
  const course = (document.getElementById("ask-course") as HTMLSelectElement).value || null;
  const answerEl = document.getElementById("answer")!;
  answerEl.innerHTML = '<p><span class="spinner"></span> Thinking… (the model can take a while)</p>';
  try {
    const res = await postJSON<QueryResult>("/api/query", { question: q, course });
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
    <h1>Lint</h1>
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
  try {
    const issues = await getJSON<LintIssue[]>("/api/lint?deep=" + (deep ? "true" : "false"));
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
