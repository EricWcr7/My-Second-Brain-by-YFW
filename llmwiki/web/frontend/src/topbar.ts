import { escapeHtml } from "./api";
import { sectionLabel, sectionPathLabel } from "./sections";
import { state } from "./state";

export function setBreadcrumb(chain: string[], leafLabel?: string): void {
  const el = document.getElementById("crumbs");
  if (!el) return;
  const visible = chain.filter((node, index) => !(node === "" && chain.length > 1 && index === 0));
  const parts = visible.map((node, index) => {
    const last = index === visible.length - 1;
    const label = escapeHtml(sectionLabel(node));
    if (last && !leafLabel) return `<span class="crumb crumb-current">${label}</span>`;
    return `<a class="crumb" href="#/section/${encodeURI(node)}">${label}</a>`;
  });
  if (leafLabel) parts.push(`<span class="crumb crumb-current">${escapeHtml(leafLabel)}</span>`);
  el.innerHTML = parts.join('<span class="crumb-sep">›</span>');
  updateScopeChip();
}

export function setScopedBreadcrumb(scope: string, viewLabel: string): void {
  const chain = scope ? scope.split("/").map((_, index, segments) => segments.slice(0, index + 1).join("/")) : [""];
  setBreadcrumb(chain, viewLabel);
}

export function updateScopeChip(): void {
  const chip = document.getElementById("scope-chip");
  if (chip) chip.textContent = sectionPathLabel(state.scope);
  const settings = document.getElementById("scope-settings-link") as HTMLAnchorElement | null;
  if (settings) settings.href = "#/customize/" + encodeURI(state.scope);
  const refresh = document.getElementById("scope-refresh") as HTMLButtonElement | null;
  if (refresh) {
    refresh.disabled = !state.meta.has_api_key;
    refresh.title = state.meta.has_api_key
      ? `Regenerate the ${sectionLabel(state.scope)} overview`
      : `${state.meta.api_key_env || "OPENAI_API_KEY"} is required`;
  }
}

export function updateKeyStatus(): void {
  const button = document.getElementById("key-status") as HTMLButtonElement | null;
  const popover = document.getElementById("readiness-popover");
  if (!button || !popover) return;
  const apiReady = state.meta.has_api_key;
  button.dataset.state = apiReady ? "ready" : "limited";
  const label = button.querySelector(".readiness-label");
  if (label) label.textContent = apiReady ? "AI ready" : "Local only";
  const summary = apiReady
    ? "Browse, search, compile, ask, and deep review are ready."
    : `Browse, local search, and structural review are ready. Set ${state.meta.api_key_env || "OPENAI_API_KEY"} to enable AI actions.`;
  button.setAttribute("aria-label", summary);
  popover.innerHTML = `
    <p class="eyebrow">System status</p>
    <h3>${apiReady ? "AI operations ready" : "Local workspace ready"}</h3>
    <p>${escapeHtml(summary)}</p>
    <div class="readiness-list">
      ${statusRow("Local vault", true, "Compiled and indexed on this machine")}
      ${statusRow("Ask & compile", apiReady, apiReady ? "Provider key detected" : `Requires ${state.meta.api_key_env || "OPENAI_API_KEY"}`)}
    </div>`;
}

function statusRow(label: string, ready: boolean, detail: string): string {
  return `<div class="readiness-row"><i class="ph ${ready ? "ph-check-circle" : "ph-info"}" aria-hidden="true"></i><span><strong>${escapeHtml(label)}</strong><small>${escapeHtml(detail)}</small></span></div>`;
}
