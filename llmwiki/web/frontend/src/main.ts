import "./phosphor.css";
import "./styles.css";

import { getJSON } from "./api";
import { initBrainField } from "./brain";
import { filterEl } from "./dom";
import { initDrawer } from "./drawer";
import { renderLandingStats } from "./landing";
import { goToPage, initRouter, navigate } from "./router";
import { restoreScope } from "./scope-state";
import { initScopeManager } from "./scope-manager";
import { loadPages, renderPageList } from "./sidebar";
import { initShell } from "./shell";
import { state, type Meta } from "./state";
import { initThemeToggle } from "./theme";
import { updateKeyStatus, updateScopeChip } from "./topbar";
import { initCommandPalette } from "./workspace";

const viewHash: Record<string, string> = {
  workspace: "#/",
  home: "#/overview",
  ask: "#/ask",
  solver: "#/solver",
  lint: "#/lint",
  ingest: "#/ingest",
};

initThemeToggle();
initDrawer();
initShell();
initScopeManager();
initCommandPalette();
initBrainField();

document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) =>
  button.addEventListener("click", () => navigate(viewHash[button.dataset.view!] ?? "#/")));

filterEl.addEventListener("input", renderPageList);

document.addEventListener("click", (event) => {
  const navEl = (event.target as Element).closest<HTMLElement>("[data-nav]");
  if (!navEl) return;
  event.preventDefault();
  const spec = navEl.dataset.nav!;
  const separator = spec.indexOf(":");
  const kind = separator < 0 ? spec : spec.slice(0, separator);
  const value = separator < 0 ? "" : spec.slice(separator + 1);
  if (kind === "page") goToPage(value);
  else if (kind === "section") navigate("#/section/" + value);
});

(async function init() {
  try {
    state.meta = await getJSON<Meta>("/api/meta");
  } catch {
    // The readiness control explains that only local shell content is available.
  }
  restoreScope();
  document.querySelectorAll<HTMLElement>('[data-view="solver"]').forEach((item) =>
    item.toggleAttribute("hidden", !state.meta.solver_enabled));
  updateKeyStatus();
  updateScopeChip();
  renderLandingStats();
  await loadPages();
  initRouter();
})();
