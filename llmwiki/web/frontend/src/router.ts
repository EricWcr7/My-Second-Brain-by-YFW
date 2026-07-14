import { closeDrawer } from "./drawer";
import { setActiveScope } from "./scope-state";
import { toast } from "./toast";
import { loadPage, renderCustomize, renderIngestSheet, setView } from "./views";
import { renderWorkspace } from "./workspace";
import { state } from "./state";

export function navigate(hash: string): void {
  if (location.hash === hash) applyRoute();
  else location.hash = hash;
}

export function goToPage(slug: string): void {
  if (state.slugSet.has(slug)) navigate("#/page/" + encodeURIComponent(slug));
  else toast(`No page “${slug}” in your wiki yet.`);
}

export function applyRoute(): void {
  closeDrawer();
  const route = location.hash.replace(/^#/, "") || "/";
  const root = document.documentElement;

  if (route === "/welcome") {
    closeTransientDialogs();
    root.dataset.screen = "welcome";
    return;
  }

  root.dataset.screen = "app";
  if (route !== "/ingest") closeDialog("source-sheet");

  if (route === "/") renderWorkspace();
  else if (route === "/overview") setView("home");
  else if (route === "/ask") setView("ask");
  else if (route === "/lint") setView("lint");
  else if (route === "/ingest") {
    renderWorkspace();
    renderIngestSheet();
  } else if (route.startsWith("/page/")) void loadPage(decodeURIComponent(route.slice("/page/".length)));
  else if (route === "/customize" || route.startsWith("/customize/")) {
    void renderCustomize(decodeURIComponent(route.replace(/^\/customize\/?/, "")));
  } else if (route.startsWith("/section/")) {
    setActiveScope(decodeURIComponent(route.slice("/section/".length)));
    renderWorkspace();
  } else {
    history.replaceState(null, "", "#/" );
    renderWorkspace();
  }
}

export function initRouter(): void {
  if (!location.hash) history.replaceState(null, "", "#/welcome");
  window.addEventListener("hashchange", applyRoute);
  applyRoute();
}

function closeTransientDialogs(): void {
  ["source-sheet", "scope-sheet", "command-palette"].forEach(closeDialog);
}

function closeDialog(id: string): void {
  const dialog = document.getElementById(id) as HTMLDialogElement | null;
  if (dialog?.open) dialog.close();
}
