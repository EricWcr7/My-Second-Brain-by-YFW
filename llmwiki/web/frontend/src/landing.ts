// Fill the landing-page stats strip from already-loaded metadata.
import { state } from "./state";

export function renderLandingStats(): void {
  const set = (id: string, value: number) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  };
  set("stat-concepts", state.meta.concept_count);
  set("stat-sources", state.meta.source_count);
}
