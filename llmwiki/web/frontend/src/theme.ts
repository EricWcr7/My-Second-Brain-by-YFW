// Light/dark toggle. The choice persists in localStorage and overrides the OS
// setting; when unset the CSS follows `prefers-color-scheme`.

export function effectiveTheme(): "light" | "dark" {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function initThemeToggle(): void {
  const updateIcons = () => {
    const dark = effectiveTheme() === "dark";
    document.querySelectorAll<HTMLElement>("[data-theme-toggle] i").forEach((icon) => {
      icon.className = `ph ${dark ? "ph-moon" : "ph-sun"}`;
    });
  };
  document.querySelectorAll<HTMLElement>("[data-theme-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const next = effectiveTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (e) {
        /* private mode */
      }
      updateIcons();
    }),
  );
  window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", updateIcons);
  updateIcons();
}
