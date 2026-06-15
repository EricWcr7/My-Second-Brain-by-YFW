// Light/dark toggle. The choice persists in localStorage and overrides the OS
// setting; when unset the CSS follows `prefers-color-scheme`.

export function effectiveTheme(): "light" | "dark" {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function initThemeToggle(): void {
  // There can be several toggles (landing top bar + sidebar); wire them all.
  document.querySelectorAll<HTMLElement>("[data-theme-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const next = effectiveTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (e) {
        /* private mode */
      }
    }),
  );
}
