import { postJSON } from "./api";
import { state } from "./state";
import { toast } from "./toast";

export function initShell(): void {
  wireMenu("brand-menu-toggle", "brand-menu");
  wireMenu("scope-menu-toggle", "scope-menu");
  wireMenu("key-status", "readiness-popover");

  document.getElementById("add-source")?.addEventListener("click", () => (location.hash = "#/ingest"));
  document.getElementById("scope-manage")?.addEventListener("click", () => {
    closeMenus();
    window.dispatchEvent(new CustomEvent("llmwiki:manage-scopes"));
  });
  document.getElementById("scope-refresh")?.addEventListener("click", async () => {
    closeMenus();
    if (!state.meta.has_api_key) {
      toast(`${state.meta.api_key_env || "OPENAI_API_KEY"} is required to regenerate overviews.`);
      return;
    }
    const button = document.getElementById("scope-refresh") as HTMLButtonElement;
    button.disabled = true;
    try {
      await postJSON("/api/overview/refresh", { section: state.scope });
      toast("Overview regenerated");
      location.hash = "#/overview";
    } catch (error) {
      toast((error as Error).message);
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target as Element;
    if (!target.closest(".brand-menu-wrap, .scope-context, .topbar-actions")) closeMenus();
    if (target.closest("[data-close-on-nav]")) {
      const dialog = target.closest("dialog") as HTMLDialogElement | null;
      dialog?.close();
    }
  });
  window.addEventListener("hashchange", closeMenus);
}

function wireMenu(toggleId: string, menuId: string): void {
  const toggle = document.getElementById(toggleId) as HTMLButtonElement | null;
  const menu = document.getElementById(menuId);
  if (!toggle || !menu) return;
  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = menu.hidden;
    closeMenus();
    menu.hidden = !willOpen;
    toggle.setAttribute("aria-expanded", String(willOpen));
  });
}

function closeMenus(): void {
  ["brand-menu", "scope-menu", "readiness-popover"].forEach((id) => {
    const menu = document.getElementById(id);
    if (menu) menu.hidden = true;
  });
  ["brand-menu-toggle", "scope-menu-toggle", "key-status"].forEach((id) =>
    document.getElementById(id)?.setAttribute("aria-expanded", "false"));
}
