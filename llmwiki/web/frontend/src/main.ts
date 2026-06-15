import "./styles.css";

import { getJSON } from "./api";
import { filterEl } from "./dom";
import { state, type Meta } from "./state";
import { loadPages, renderPageList } from "./sidebar";
import { initThemeToggle } from "./theme";
import { initRouter, navigate, applyRoute } from "./router";
import { renderLandingStats } from "./landing";

// Sidebar nav buttons map to routes. Landing CTAs/cards/logo are plain
// <a href="#/…"> anchors, so the browser updates the hash and the router
// reacts — no JS needed for those.
const viewHash: Record<string, string> = {
  home: "#/overview",
  ask: "#/ask",
  lint: "#/lint",
};

initThemeToggle();

document.querySelectorAll<HTMLButtonElement>("#nav button").forEach((b) =>
  b.addEventListener("click", () => navigate(viewHash[b.dataset.view!] ?? "#/overview")));

filterEl.addEventListener("input", renderPageList);

// Delegated clicks for elements that aren't hash anchors: sidebar page links,
// wikilinks, and lint page refs. All funnel through the router.
document.addEventListener("click", (e) => {
  const target = e.target as Element;
  // Scope picker: set the active scope, then re-render the list and the current
  // view so Ask/Lint reflect the new slice.
  const scopeNode = target.closest<HTMLAnchorElement>("#pages a[data-scope]");
  if (scopeNode) {
    state.scope = scopeNode.dataset.scope ?? "";
    renderPageList();
    applyRoute();
    return;
  }
  const side = target.closest<HTMLAnchorElement>("#pages a[data-slug]");
  if (side) {
    navigate("#/page/" + side.dataset.slug);
    return;
  }
  const wl = target.closest<HTMLAnchorElement>("a.wikilink");
  if (wl) {
    e.preventDefault();
    navigate("#/page/" + wl.dataset.slug);
    return;
  }
  const lp = target.closest<HTMLElement>(".lint-page");
  if (lp && state.slugSet.has(lp.dataset.slug!)) {
    navigate("#/page/" + lp.dataset.slug);
    return;
  }
});

(async function init() {
  try {
    state.meta = await getJSON<Meta>("/api/meta");
  } catch (err) {
    /* keep defaults */
  }
  renderLandingStats();
  await loadPages();
  initRouter(); // applies the current hash (landing by default)
})();
