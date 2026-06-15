// Hash routing. The hash is the single source of truth: navigate() sets it and
// the hashchange listener applies it. Routes:
//   #/            -> landing screen
//   #/overview    -> app, Overview view
//   #/ask         -> app, Ask view
//   #/lint        -> app, Lint view
//   #/page/<slug> -> app, that page
import { setView, loadPage } from "./views";

export function navigate(hash: string): void {
  if (location.hash === hash) applyRoute(); // same hash won't fire hashchange
  else location.hash = hash;
}

export function applyRoute(): void {
  const route = location.hash.replace(/^#/, "");
  const root = document.documentElement;

  if (!route || route === "/") {
    root.setAttribute("data-screen", "landing");
    return;
  }

  root.setAttribute("data-screen", "app");
  if (route === "/overview") setView("home");
  else if (route === "/ask") setView("ask");
  else if (route === "/lint") setView("lint");
  else if (route.startsWith("/page/")) loadPage(decodeURIComponent(route.slice("/page/".length)));
  else root.setAttribute("data-screen", "landing"); // unknown route -> landing
}

export function initRouter(): void {
  window.addEventListener("hashchange", applyRoute);
  applyRoute();
}
