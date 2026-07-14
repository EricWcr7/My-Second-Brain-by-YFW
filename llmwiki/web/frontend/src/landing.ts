import { state } from "./state";

// The welcome screen deliberately stays simple: it reflects local vault counts
// and sends the user into the operational workspace.
export function renderLandingStats(): void {
  const set = (id: string, value: number) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  };
  set("stat-concepts", state.meta.concept_count);
  set("stat-sources", state.meta.source_count);
}
