import { getJSON, escapeHtml } from "./api";
import { pagesEl, filterEl } from "./dom";
import { state, type PageRef } from "./state";

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

export function renderPageList(): void {
  const q = filterEl.value.trim().toLowerCase();
  const groups: Record<string, PageRef[]> = {};
  for (const p of state.pages) {
    if (q && !p.title.toLowerCase().includes(q) && !p.slug.includes(q)) continue;
    (groups[p.course] = groups[p.course] || []).push(p);
  }
  const courses = Object.keys(groups).sort();
  if (!courses.length) {
    pagesEl.innerHTML = '<p class="muted">No pages. Ingest sources from the CLI.</p>';
    return;
  }
  let html = "";
  for (const course of courses) {
    html += `<div class="course">${escapeHtml(course)}</div>`;
    for (const p of groups[course].sort((a, b) => a.title.localeCompare(b.title))) {
      html +=
        `<a data-slug="${escapeHtml(p.slug)}">${escapeHtml(p.title)}` +
        `<span class="badge">${p.type === "source" ? "src" : ""}</span></a>`;
    }
  }
  pagesEl.innerHTML = html;
}

export function highlightSidebar(slug: string | null): void {
  pagesEl.querySelectorAll<HTMLAnchorElement>("a").forEach((a) =>
    a.classList.toggle("active", a.dataset.slug === slug));
}
