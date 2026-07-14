import { delJSON, escapeHtml, getJSON, postJSON } from "./api";
import { confirmDialog } from "./confirm-dialog";
import { renderLandingStats } from "./landing";
import { setActiveScope } from "./scope-state";
import { sectionContains, sectionLabel, sectionPathLabel, scopeNodes } from "./sections";
import { loadPages } from "./sidebar";
import { state, type Meta } from "./state";
import { toast } from "./toast";

const PROTECTED = new Set(["", "academic"]);

export function initScopeManager(): void {
  const dialog = document.getElementById("scope-sheet") as HTMLDialogElement;
  window.addEventListener("llmwiki:manage-scopes", () => openScopeManager());
  dialog.querySelector("[data-close-sheet]")?.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}

export function openScopeManager(): void {
  const dialog = document.getElementById("scope-sheet") as HTMLDialogElement;
  renderScopeManager();
  if (!dialog.open) dialog.showModal();
}

function renderScopeManager(): void {
  const body = document.getElementById("scope-sheet-body")!;
  const nodes = scopeNodes(["academic", ...state.meta.sections]);
  const parents = nodes.filter((node) => !sectionContains("academic", node) || node === "academic");
  body.innerHTML = `
    <header class="sheet-title">
      <p class="eyebrow">Knowledge structure</p>
      <h2>Manage scopes</h2>
      <p>Create branches and courses, or remove a scope and everything filed beneath it.</p>
    </header>
    <div class="scope-manager-grid">
      <form id="scope-create-form" class="scope-create-panel">
        <div class="scope-create-icon"><i class="ph ph-tree-structure" aria-hidden="true"></i></div>
        <h3>Create a scope</h3>
        <label>Name<input id="scope-create-name" type="text" autocomplete="off" placeholder="e.g. Research"></label>
        <label>Parent<select id="scope-create-parent">${parents.map((node) => `<option value="${escapeHtml(node)}"${node === state.scope ? " selected" : ""}>${escapeHtml(sectionPathLabel(node))}</option>`).join("")}</select></label>
        <button class="button button-primary" type="submit"><i class="ph ph-plus" aria-hidden="true"></i>Create scope</button>
        <p id="scope-create-error" class="form-error" aria-live="polite"></p>
      </form>
      <section class="scope-list-panel">
        <div class="scope-list-head"><span>Scope</span><span>Pages</span><span></span></div>
        <div class="scope-manager-list">${nodes.map((node) => scopeRow(node)).join("")}</div>
      </section>
    </div>`;

  document.getElementById("scope-create-form")?.addEventListener("submit", createScope);
  body.querySelectorAll<HTMLButtonElement>("[data-delete-scope]").forEach((button) =>
    button.addEventListener("click", () => deleteScope(button.dataset.deleteScope!)));
}

function scopeRow(scope: string): string {
  const count = state.pages.filter((page) => sectionContains(scope, page.section)).length;
  const depth = scope ? scope.split("/").length : 0;
  const disabled = PROTECTED.has(scope);
  return `<div class="scope-manager-row" style="--scope-depth:${depth}">
    <a href="#/section/${encodeURI(scope)}" data-close-on-nav><i class="ph ${scope === "" ? "ph-globe-hemisphere-west" : "ph-folder"}" aria-hidden="true"></i><span><strong>${escapeHtml(sectionLabel(scope))}</strong><small>${escapeHtml(sectionPathLabel(scope))}</small></span></a>
    <span>${count}</span>
    ${disabled ? `<span class="scope-protected">Protected</span>` : `<button class="icon-button danger-icon" type="button" data-delete-scope="${escapeHtml(scope)}" aria-label="Delete ${escapeHtml(sectionLabel(scope))}"><i class="ph ph-trash" aria-hidden="true"></i></button>`}
  </div>`;
}

async function createScope(event: Event): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const input = document.getElementById("scope-create-name") as HTMLInputElement;
  const parent = (document.getElementById("scope-create-parent") as HTMLSelectElement).value;
  const error = document.getElementById("scope-create-error")!;
  const name = input.value.trim();
  if (!name) {
    error.textContent = "Enter a scope name.";
    input.focus();
    return;
  }
  const submit = form.querySelector("button[type=submit]") as HTMLButtonElement;
  submit.disabled = true;
  error.textContent = "";
  try {
    const result = await postJSON<{ section: string }>("/api/sections", { name, parent });
    await refreshState();
    setActiveScope(result.section);
    (document.getElementById("scope-sheet") as HTMLDialogElement).close();
    location.hash = "#/section/" + encodeURI(result.section);
    toast(`Created ${sectionLabel(result.section)}`);
  } catch (reason) {
    error.textContent = (reason as Error).message;
    submit.disabled = false;
  }
}

async function deleteScope(scope: string): Promise<void> {
  const label = sectionLabel(scope);
  const confirmed = await confirmDialog({
    eyebrow: "Delete scope",
    title: `Delete ${label}?`,
    message: "Every concept, source, cached file, override, and search entry in this scope and its descendants will be permanently removed.",
    typedValue: label,
    confirmLabel: "Delete scope",
  });
  if (!confirmed) return;
  try {
    await delJSON("/api/sections/" + scope.split("/").map(encodeURIComponent).join("/"));
    if (sectionContains(scope, state.scope)) setActiveScope("");
    await refreshState();
    renderScopeManager();
    toast(`Deleted ${label}`);
  } catch (reason) {
    toast((reason as Error).message);
  }
}

async function refreshState(): Promise<void> {
  state.meta = await getJSON<Meta>("/api/meta");
  await loadPages();
  renderLandingStats();
}
