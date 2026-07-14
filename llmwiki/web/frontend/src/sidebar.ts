import { getJSON, escapeHtml } from "./api";
import { pagesEl, filterEl } from "./dom";
import { state, type PageRef } from "./state";
import {
  sectionContains,
  sectionLabel,
  sectionSegments,
  scopeNodes,
} from "./sections";

export async function loadPages(): Promise<void> {
  try {
    state.pages = await getJSON<PageRef[]>("/api/pages");
    state.slugSet = new Set(state.pages.map((p) => p.slug));
  } catch (err) {
    pagesEl.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
    return;
  }
  renderPageList();
}

// The scope tree: General root + every section (and ancestors). Selecting a node
// sets the scope that drives the page list and the Ask/Lint operations — so every
// level offers the same operations over a different slice of the base.
function renderScopeTree(): string {
  const nodes = scopeNodes(state.meta.sections);
  let html = '<div class="scope-tree"><div class="scope-head">Scope</div>';
  for (const node of nodes) {
    const depth = sectionSegments(node).length;
    const count = state.pages.filter((p) => sectionContains(node, p.section)).length;
    const active = node === state.scope ? " active" : "";
    html +=
      `<a class="scope-node${active}" href="#/section/${node}" ` +
      `style="padding-left:${10 + depth * 14}px">` +
      `${escapeHtml(sectionLabel(node))}<span class="scope-count">${count}</span></a>`;
  }
  return html + "</div>";
}

export function renderPageList(): void {
  const q = filterEl.value.trim().toLowerCase();
  const groups: Record<string, PageRef[]> = {};
  for (const p of state.pages) {
    if (!sectionContains(state.scope, p.section)) continue;
    if (q && !p.title.toLowerCase().includes(q) && !p.slug.includes(q)) continue;
    (groups[p.section] = groups[p.section] || []).push(p);
  }
  let html = renderScopeTree();
  const sections = Object.keys(groups).sort();
  if (!sections.length) {
    html += '<p class="muted">No pages in this scope yet. Use the Ingest view to add sources.</p>';
    pagesEl.innerHTML = html;
    return;
  }
  for (const section of sections) {
    html += `<div class="section">${escapeHtml(section || "General")}</div>`;
    for (const p of groups[section].sort((a, b) => a.title.localeCompare(b.title))) {
      // Distinguish non-concept pages (source, query, overview, schema) with a
      // small mono type tag; concept pages — the common case — stay untagged.
      const tag = p.type && p.type !== "concept" ? p.type : "";
      html +=
        `<a data-slug="${escapeHtml(p.slug)}" href="#/page/${encodeURIComponent(p.slug)}">` +
        `<span class="page-title">${escapeHtml(p.title)}</span>` +
        `<span class="badge">${escapeHtml(tag)}</span></a>`;
    }
  }
  pagesEl.innerHTML = html;
}

export function highlightSidebar(slug: string | null): void {
  pagesEl.querySelectorAll<HTMLAnchorElement>("a[data-slug]").forEach((a) =>
    a.classList.toggle("active", a.dataset.slug === slug));
}
