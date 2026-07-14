import { escapeHtml, getJSON, postJSON } from "./api";
import { content } from "./dom";
import { sectionAncestors, sectionContains, sectionLabel, sectionPathLabel } from "./sections";
import { state, type PageRef } from "./state";
import { setBreadcrumb } from "./topbar";
import { toast } from "./toast";

interface SearchHit {
  slug: string;
  title: string;
  section: string;
  score: number;
}

let searchTimer = 0;
let searchRequest = 0;

export function renderWorkspace(): void {
  setActiveNavigation("workspace");
  setBreadcrumb(sectionAncestors(state.scope));
  const label = state.scope ? sectionPathLabel(state.scope) : "General";
  content.className = "workspace-view";
  content.innerHTML = `
    <section class="workspace-head">
      <div>
        <p class="eyebrow">Scope</p>
        <h1>${escapeHtml(label)}</h1>
      </div>
      <button class="button button-quiet workspace-review" type="button" data-command="lint">
        <i class="ph ph-check" aria-hidden="true"></i>Review scope
      </button>
    </section>
    <section class="command-surface">
      <div class="workspace-command-input">
        <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
        <input id="workspace-query" type="search" autocomplete="off" placeholder="Search, ask, or run an action…" aria-label="Search this scope">
        <kbd>/</kbd>
        <button class="command-submit" type="button" aria-label="Open first result"><i class="ph ph-arrow-right" aria-hidden="true"></i></button>
      </div>
      <p class="command-try"><strong>Try:</strong> key ideas <span>·</span> examples <span>·</span> gaps <span>·</span> source titles</p>
    </section>
    <div id="workspace-results" class="workspace-results"></div>`;

  const input = document.getElementById("workspace-query") as HTMLInputElement;
  const results = document.getElementById("workspace-results")!;
  paintResults(results, "", []);
  input.addEventListener("input", () => scheduleSearch(input.value, results));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      activateFirst(results);
    } else if (event.key === "Escape" && input.value) {
      input.value = "";
      paintResults(results, "", []);
    }
  });
  document.querySelector<HTMLButtonElement>(".command-submit")?.addEventListener("click", () => activateFirst(results));
  wireCommands(content);
}

export function initCommandPalette(): void {
  const dialog = document.getElementById("command-palette") as HTMLDialogElement;
  const input = document.getElementById("palette-input") as HTMLInputElement;
  const results = document.getElementById("palette-results")!;
  const open = () => {
    if (!dialog.open) dialog.showModal();
    input.value = "";
    paintResults(results, "", []);
    requestAnimationFrame(() => input.focus());
  };

  document.getElementById("global-search")?.addEventListener("click", open);
  document.addEventListener("keydown", (event) => {
    const target = event.target as HTMLElement;
    const editing = target.matches("input, textarea, select, [contenteditable=true]");
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      open();
      return;
    }
    if (event.key === "/" && !editing && document.documentElement.dataset.screen === "app") {
      const workspaceInput = document.getElementById("workspace-query") as HTMLInputElement | null;
      if (workspaceInput) {
        event.preventDefault();
        workspaceInput.focus();
      }
    }
  });
  input.addEventListener("input", () => scheduleSearch(input.value, results));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      activateFirst(results);
    } else if (event.key === "Escape") {
      event.preventDefault();
      dialog.close();
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
    else if ((event.target as Element).closest("a[data-result]")) dialog.close();
  });
  dialog.addEventListener("close", () => {
    input.value = "";
    clearTimeout(searchTimer);
  });
  wireCommands(dialog);
}

export function setActiveNavigation(view: string): void {
  document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) =>
    button.classList.toggle("active", button.dataset.view === view));
}

function scheduleSearch(query: string, target: HTMLElement): void {
  clearTimeout(searchTimer);
  const normalized = query.trim();
  const request = ++searchRequest;
  paintResults(target, normalized, []);
  if (normalized.length < 2) return;
  searchTimer = window.setTimeout(async () => {
    const params = new URLSearchParams({ q: normalized });
    if (state.scope) params.set("section", state.scope);
    try {
      const hits = await getJSON<SearchHit[]>(`/api/search?${params}`);
      if (request === searchRequest) paintResults(target, normalized, hits);
    } catch {
      // Local results remain fully usable if semantic search is unavailable.
    }
  }, 250);
}

function paintResults(target: HTMLElement, query: string, remote: SearchHit[]): void {
  const scoped = state.pages.filter((page) => sectionContains(state.scope, page.section));
  const normalized = query.toLowerCase();
  const local = normalized
    ? scoped
        .filter((page) => page.title.toLowerCase().includes(normalized) || page.slug.toLowerCase().includes(normalized))
        .sort((a, b) => localRank(a, normalized) - localRank(b, normalized) || a.title.localeCompare(b.title))
    : scoped.slice().sort((a, b) => a.title.localeCompare(b.title));
  const bySlug = new Map<string, PageRef>();
  local.forEach((page) => bySlug.set(page.slug, page));
  remote.forEach((hit) => {
    const page = state.pages.find((candidate) => candidate.slug === hit.slug);
    if (page && sectionContains(state.scope, page.section) && !bySlug.has(page.slug)) bySlug.set(page.slug, page);
  });
  const pages = [...bySlug.values()];
  const concepts = pages.filter((page) => page.type === "concept").slice(0, query ? 10 : 6);
  const sources = pages.filter((page) => page.type !== "concept").slice(0, query ? 8 : 4);
  const actions = actionRows(query);

  let html = actions;
  html += resultGroup("Concepts in this scope", concepts, "concept");
  html += resultGroup("Sources in this scope", sources, "source");
  if (!concepts.length && !sources.length && query) {
    html += `<div class="workspace-empty"><i class="ph ph-magnifying-glass" aria-hidden="true"></i><h2>No matches in this scope</h2><p>Try a different phrase, switch scope, or ask the model.</p><button class="button button-primary" type="button" data-command="ask">Ask in ${escapeHtml(sectionLabel(state.scope))}</button></div>`;
  } else if (!concepts.length && !sources.length) {
    html += `<div class="workspace-empty"><i class="ph ph-upload-simple" aria-hidden="true"></i><h2>This scope is ready for its first source</h2><p>Compile a file or URL into connected concepts.</p><button class="button button-primary" type="button" data-command="ingest">Add source</button></div>`;
  }
  target.innerHTML = html;
  wireCommands(target);
}

function actionRows(query: string): string {
  const label = escapeHtml(sectionLabel(state.scope));
  const queryHint = query ? ` for “${escapeHtml(query)}”` : "";
  return `<section class="result-group command-actions">
    <h2>Actions</h2>
    <div class="action-grid">
      <button type="button" data-command="ingest" data-result><i class="ph ph-upload-simple" aria-hidden="true"></i><span><strong>Add source</strong><small>Compile a file or URL into ${label}</small></span></button>
      <button type="button" data-command="ask" data-result><i class="ph ph-chat-centered-text" aria-hidden="true"></i><span><strong>Ask${queryHint}</strong><small>Ground an answer in this scope</small></span></button>
      <button type="button" data-command="lint" data-result><i class="ph ph-check" aria-hidden="true"></i><span><strong>Review scope</strong><small>Find broken links, orphans, and gaps</small></span></button>
      <button type="button" data-command="refresh" data-result><i class="ph ph-arrows-clockwise" aria-hidden="true"></i><span><strong>Refresh overview</strong><small>Regenerate the current scope summary</small></span></button>
      <button type="button" data-command="manage" data-result><i class="ph ph-tree-structure" aria-hidden="true"></i><span><strong>Manage scopes</strong><small>Create or remove knowledge branches</small></span></button>
    </div>
  </section>`;
}

function resultGroup(label: string, pages: PageRef[], kind: "concept" | "source"): string {
  if (!pages.length) return "";
  const icon = kind === "concept" ? "ph-file-text" : "ph-file";
  return `<section class="result-group"><h2>${label}</h2><div class="knowledge-list">${pages.map((page) => `
    <a href="#/page/${encodeURIComponent(page.slug)}" data-result>
      <i class="ph ${icon}" aria-hidden="true"></i>
      <strong>${escapeHtml(page.title)}</strong>
      <span>${escapeHtml(page.section ? sectionPathLabel(page.section) : "General")}</span>
      <small>${escapeHtml(page.type)}</small>
      <i class="ph ph-arrow-right row-arrow" aria-hidden="true"></i>
    </a>`).join("")}</div></section>`;
}

function localRank(page: PageRef, query: string): number {
  const title = page.title.toLowerCase();
  const slug = page.slug.toLowerCase();
  if (title === query || slug === query) return 0;
  if (title.startsWith(query) || slug.startsWith(query)) return 1;
  return 2;
}

function activateFirst(target: HTMLElement): void {
  const first = target.querySelector<HTMLElement>("[data-result]");
  first?.click();
}

function wireCommands(root: ParentNode): void {
  root.querySelectorAll<HTMLElement>("[data-command]").forEach((element) => {
    if (element.dataset.wired === "true") return;
    element.dataset.wired = "true";
    element.addEventListener("click", async () => {
      const dialog = element.closest("dialog") as HTMLDialogElement | null;
      dialog?.close();
      const command = element.dataset.command;
      if (command === "ingest") location.hash = "#/ingest";
      else if (command === "ask") location.hash = "#/ask";
      else if (command === "lint") location.hash = "#/lint";
      else if (command === "manage") window.dispatchEvent(new CustomEvent("llmwiki:manage-scopes"));
      else if (command === "overview") location.hash = "#/overview";
      else if (command === "refresh") {
        if (!state.meta.has_api_key) {
          toast(`${state.meta.api_key_env || "OPENAI_API_KEY"} is required to regenerate overviews.`);
          return;
        }
        try {
          await postJSON("/api/overview/refresh", { section: state.scope });
          toast("Overview regenerated");
          location.hash = "#/overview";
        } catch (error) {
          toast((error as Error).message);
        }
      }
    });
  });
}
