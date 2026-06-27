// Landing-page hydration: the live stats strip and the dynamic branch cards.
import { postJSON, escapeHtml } from "./api";
import { state } from "./state";
import { childSections, sectionContains, sectionLabel } from "./sections";

export function renderLandingStats(): void {
  const set = (id: string, value: number) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  };
  set("stat-concepts", state.meta.concept_count);
  set("stat-sources", state.meta.source_count);
}

// One "Browse by branch" card. Academic carries tailored copy; every other
// top-level branch (the ones you add) shares a generic line, so a new branch
// reads as a first-class sibling the moment it's created.
function branchCard(branch: string): string {
  const label = escapeHtml(sectionLabel(branch));
  const icon = branch === "academic" ? "academic" : "branch";
  const n = state.pages.filter((p) => sectionContains(branch, p.section)).length;
  const count = `${n} ${n === 1 ? "page" : "pages"}`;
  const lead =
    branch === "academic"
      ? "All your courses’ knowledge — open a course or ask across every course."
      : `Everything filed under ${label} — scoped to this branch and beneath.`;
  return (
    `<a class="lp-card" href="#/section/${branch}">` +
    `<span class="lp-card-icon" data-icon="${icon}"></span>` +
    `<h3>${label}</h3>` +
    `<p>${lead}</p>` +
    `<span class="lp-card-go">Open ${label} · ${count} →</span>` +
    `</a>`
  );
}

// Fill the "Browse by branch" grid from the top-level sections. The seeded
// `academic` branch is always shown (even on a fresh vault); the rest are the
// branches you've added, sorted so they slot in beside Academic one-by-one.
export function renderBranches(): void {
  const wrap = document.getElementById("lp-branches");
  if (!wrap) return;
  const branches = [
    ...new Set(["academic", ...childSections("", state.meta.sections)]),
  ].sort();
  wrap.innerHTML = branches.map(branchCard).join("");
}

// Wire the "+ New branch" control (static markup in index.html): toggle the
// inline form, POST a top-level section (parent = "" → the General root), then
// re-render so the new card appears beside Academic without leaving the home page.
export function wireNewBranch(): void {
  const btn = document.getElementById("lp-new-branch-btn");
  const form = document.getElementById("lp-new-branch-form") as HTMLFormElement | null;
  const nameInput = document.getElementById("lp-new-branch-name") as HTMLInputElement | null;
  const cancel = document.getElementById("lp-new-branch-cancel");
  const errBox = document.getElementById("lp-new-branch-error");
  if (!btn || !form || !nameInput || !cancel || !errBox) return;

  const reset = () => {
    form.hidden = true;
    errBox.innerHTML = "";
    nameInput.value = "";
  };
  btn.addEventListener("click", () => {
    form.hidden = !form.hidden;
    if (!form.hidden) nameInput.focus();
  });
  cancel.addEventListener("click", reset);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    if (!name) return;
    errBox.innerHTML = "";
    try {
      const res = await postJSON<{ section: string; label: string }>(
        "/api/sections",
        { name, parent: "" },
      );
      if (!state.meta.sections.includes(res.section)) {
        state.meta.sections = [...state.meta.sections, res.section].sort();
      }
      reset();
      renderBranches(); // new card appears beside Academic
    } catch (err) {
      errBox.innerHTML = `<p class="notice">${escapeHtml((err as Error).message)}</p>`;
    }
  });
}
