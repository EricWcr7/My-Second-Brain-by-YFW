// A single transient toast for navigation feedback (e.g. a wikilink or lint
// reference that points to a page not in the wiki). One element, reused.

let el: HTMLElement | null = null;
let timer: number | undefined;

export function toast(message: string): void {
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
  }
  el.textContent = message;
  // restart the enter animation even if a toast is already showing
  el.classList.remove("show");
  void el.offsetWidth;
  el.classList.add("show");
  window.clearTimeout(timer);
  timer = window.setTimeout(() => el && el.classList.remove("show"), 2600);
}
