// Off-canvas sidebar drawer for narrow screens. On mobile the sidebar is a fixed
// panel that slides in over the content; state lives in `data-drawer` on <html>
// (the CSS reacts to it). It closes on scrim click, Escape, navigation (the
// router calls closeDrawer in applyRoute), or when the viewport grows to desktop.

const root = document.documentElement;

function setDrawer(open: boolean): void {
  root.setAttribute("data-drawer", open ? "open" : "closed");
  document.getElementById("menu-toggle")?.setAttribute("aria-expanded", String(open));
}

export function closeDrawer(): void {
  if (root.getAttribute("data-drawer") === "open") setDrawer(false);
}

export function initDrawer(): void {
  document.getElementById("menu-toggle")?.addEventListener("click", () =>
    setDrawer(root.getAttribute("data-drawer") !== "open"));
  document.getElementById("scrim")?.addEventListener("click", () => setDrawer(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });
  // Growing back past the mobile breakpoint returns the sidebar to a fixed panel;
  // clear any lingering open state so it can't get stuck.
  window.matchMedia("(min-width: 701px)").addEventListener("change", (e) => {
    if (e.matches) closeDrawer();
  });
}
