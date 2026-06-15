// Hash routing. The hash is the single source of truth: navigate() sets it and
// the hashchange listener applies it. Routes:
//   #/               -> landing screen (also General, the top of the hierarchy)
//   #/overview       -> app, Overview view
//   #/ask            -> app, Ask view
//   #/lint           -> app, Lint view
//   #/page/<slug>    -> app, that page
//   #/section/<path> -> app, that section's hub (branch/course page)
import { setView, loadPage, renderSection } from "./views";
import { state } from "./state";
import { renderPageList } from "./sidebar";

export function navigate(hash: string): void {
  if (location.hash === hash) applyRoute(); // same hash won't fire hashchange
  else location.hash = hash;
}

export function applyRoute(): void {
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
  else if (route.startsWith("/page/")) loadPage(decodeURIComponent(route.slice("/page/".length)));
  else if (route.startsWith("/section/")) {
    const path = decodeURIComponent(route.slice("/section/".length));
    if (path) renderSection(path);
    else root.setAttribute("data-screen", "landing"); // General == the landing
  } else root.setAttribute("data-screen", "landing"); // unknown route -> landing
}

export function initRouter(): void {
  window.addEventListener("hashchange", applyRoute);
  applyRoute();
}
