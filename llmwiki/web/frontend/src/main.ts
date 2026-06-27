import "./styles.css";

import { getJSON } from "./api";
import { filterEl } from "./dom";
import { state, type Meta } from "./state";
import { loadPages, renderPageList } from "./sidebar";
import { initThemeToggle } from "./theme";
import { initDrawer } from "./drawer";
import { initRouter, navigate, goToPage } from "./router";
import { renderLandingStats, renderBranches, wireNewBranch } from "./landing";
import { updateScopeChip, updateKeyStatus } from "./topbar";

// Sidebar nav buttons map to routes. Landing CTAs/cards/logo are plain
// <a href="#/…"> anchors, so the browser updates the hash and the router
// reacts — no JS needed for those.
const viewHash: Record<string, string> = {
  home: "#/overview",
  ask: "#/ask",
  lint: "#/lint",
  ingest: "#/ingest",
};

initThemeToggle();
initDrawer();

document.querySelectorAll<HTMLButtonElement>("#nav button").forEach((b) =>
  b.addEventListener("click", () => navigate(viewHash[b.dataset.view!] ?? "#/overview")));

filterEl.addEventListener("input", renderPageList);

// One delegated dispatcher for the links that can't be plain hash anchors:
// in-content wikilinks and lint references. They're generated and may point at
// pages not in the wiki, so they carry `data-nav="page:<slug>"` and route through
// goToPage (which gives feedback for a missing target). Everything else that
// navigates — sidebar pages, the scope tree, breadcrumbs, hub cards, landing
// cards — is a plain `#/…` anchor the router handles natively.
document.addEventListener("click", (e) => {
  const navEl = (e.target as Element).closest<HTMLElement>("[data-nav]");
  if (!navEl) return;
  e.preventDefault();
  const spec = navEl.dataset.nav!;
  const sep = spec.indexOf(":");
  const kind = sep < 0 ? spec : spec.slice(0, sep);
  const value = sep < 0 ? "" : spec.slice(sep + 1);
  if (kind === "page") goToPage(value);
  else if (kind === "section") navigate("#/section/" + value);
});

(async function init() {
  try {
    state.meta = await getJSON<Meta>("/api/meta");
  } catch (err) {
    /* keep defaults */
  }
  renderLandingStats();
  updateKeyStatus();
  updateScopeChip();
  await loadPages();
  renderBranches(); // landing "Browse by branch" cards (needs pages for counts)
  wireNewBranch(); // "+ New branch" control on the landing
  initRouter(); // applies the current hash (landing by default)
})();
