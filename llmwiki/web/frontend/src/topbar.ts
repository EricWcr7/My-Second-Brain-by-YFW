// The persistent app top bar: a single source of wayfinding. It renders the
// breadcrumb for the current view, the working scope (with a clear control),
// and the API-key status. All of its links are plain `#/…` hash anchors, so
// they navigate the same way as the sidebar and in-content links.
import { escapeHtml } from "./api";
import { state } from "./state";
import { sectionAncestors, sectionLabel } from "./sections";

// Render the breadcrumb. `chain` is the section-node prefix (each crumb links to
// its hub at `#/section/<node>`); with `leafLabel` it's appended as the current
// (non-link) item — otherwise the last chain node is the current one. Mirrors
// the old in-content `crumbs()` semantics, now hoisted into the top bar.
export function setBreadcrumb(chain: string[], leafLabel?: string): void {
  const el = document.getElementById("crumbs");
  if (!el) return;
  const parts = chain.map((node, i) => {
    const last = i === chain.length - 1;
    const label = escapeHtml(sectionLabel(node));
    if (last && !leafLabel) return `<span class="crumb crumb-current">${label}</span>`;
    return `<a class="crumb" href="#/section/${node}">${label}</a>`; // node "" -> General hub
  });
  if (leafLabel) parts.push(`<span class="crumb crumb-current">${escapeHtml(leafLabel)}</span>`);
  el.innerHTML = parts.join('<span class="crumb-sep">›</span>');
  updateScopeChip();
}

// Convenience: breadcrumb for a scope + a view label (Ask/Lint/Ingest/Overview).
export function setScopedBreadcrumb(scope: string, viewLabel: string): void {
  setBreadcrumb(sectionAncestors(scope), viewLabel);
}

// The working-scope chip. Shows the current scope and a clear control; "" is
// General (the whole base), the implicit default, shown without a clear button.
export function updateScopeChip(): void {
  const chip = document.getElementById("scope-chip");
  if (!chip) return;
  if (!state.scope) {
    chip.className = "scope-chip";
    chip.innerHTML =
      `<span class="scope-chip-tag">Scope</span>` +
      `<a class="scope-chip-label" href="#/section/">General · all notes</a>`;
    return;
  }
  const label = escapeHtml(sectionLabel(state.scope));
  chip.className = "scope-chip scoped";
  chip.innerHTML =
    `<span class="scope-chip-tag">Scope</span>` +
    `<a class="scope-chip-label" href="#/section/${state.scope}" title="Open ${label}">${label}</a>` +
    `<a class="scope-chip-clear" href="#/section/" aria-label="Clear scope — back to General" title="Clear scope">✕</a>`;
}

// API-key status dot: a quiet readiness signal for Ask/Ingest (which need a key).
export function updateKeyStatus(): void {
  const el = document.getElementById("key-status");
  if (!el) return;
  const ok = state.meta.has_api_key;
  el.className = "key-status " + (ok ? "ok" : "off");
  const tip = ok
    ? "API key detected — Ask and Ingest are ready."
    : `No API key (${state.meta.api_key_env || "OPENAI_API_KEY"}). Browse, Search, and structural Lint still work.`;
  el.title = tip;
  el.setAttribute("aria-label", tip);
}
