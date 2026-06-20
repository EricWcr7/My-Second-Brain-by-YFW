// Hash routing. The hash is the single source of truth: navigate() sets it and
// the hashchange listener applies it. Routes:
//   #/               -> landing screen (also General, the top of the hierarchy)
//   #/overview       -> app, Overview view
//   #/ask            -> app, Ask view
//   #/lint           -> app, Lint view
//   #/ingest         -> app, Ingest view
//   #/page/<slug>    -> app, that page
//   #/section/<path> -> app, that section's hub (branch/course page)
import { setView, loadPage, renderSection } from "./views";
import { state } from "./state";
import { renderPageList } from "./sidebar";
import { toast } from "./toast";
import { closeDrawer } from "./drawer";

export function navigate(hash: string): void {
  if (location.hash === hash) applyRoute(); // same hash won't fire hashchange
  else location.hash = hash;
}

// Navigate to a page if it exists, else tell the user. Used by the in-content
// wikilinks and lint references, which can point at pages not in the wiki — so a
// click on a dangling/missing target gives feedback instead of failing silently.
export function goToPage(slug: string): void {
  if (state.slugSet.has(slug)) navigate("#/page/" + slug);
  else toast(`No page “${slug}” in your wiki yet.`);
}

export function applyRoute(): void {
  closeDrawer(); // any navigation dismisses the mobile sidebar drawer
  const route = location.hash.replace(/^#/, "");
  const root = document.documentElement;

  if (!route || route === "/") {
    root.setAttribute("data-screen", "landing");
    // The landing is General's page; reset the scope so its Overview/Ask/Lint
    // cards operate over the whole base even after visiting a branch.
    if (state.scope) {
      state.scope = "";
      renderPageList();
    }
    return;
  }

  root.setAttribute("data-screen", "app");
  if (route === "/overview") setView("home");
  else if (route === "/ask") setView("ask");
  else if (route === "/lint") setView("lint");
  else if (route === "/ingest") setView("ingest");
  else if (route.startsWith("/page/")) loadPage(decodeURIComponent(route.slice("/page/".length)));
  else if (route.startsWith("/section/")) {
    // The empty path ("#/section/") is General's hub; the full-screen landing
    // still lives at "#/" (the logo / first load).
    renderSection(decodeURIComponent(route.slice("/section/".length)));
  } else root.setAttribute("data-screen", "landing"); // unknown route -> landing
}

export function initRouter(): void {
  window.addEventListener("hashchange", applyRoute);
  applyRoute();
}
