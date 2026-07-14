import markdownit from "markdown-it";
import texmath from "markdown-it-texmath";
import katex from "katex";
import "katex/dist/katex.min.css";

import { content } from "./dom";
import { state } from "./state";

// Markdown + math renderer. texmath tokenizes $…$ / $$…$$ before markdown
// rules run, so underscores/asterisks inside formulas are never mangled.
const md = markdownit({ html: false, linkify: true, typographer: true }).use(texmath, {
  engine: katex,
  delimiters: "dollars",
  katexOptions: { throwOnError: false },
});

export function preprocessWikilinks(text: string): string {
  // [[slug]], [[slug|Alias]], [[slug#Heading|Alias]] -> markdown link (wiki: scheme)
  return (text || "").replace(/\[\[([^\]]+)\]\]/g, (_, inner: string) => {
    const parts = inner.split("|");
    const slug = parts[0].split("#")[0].trim();
    const label = (parts[1] || parts[0]).trim();
    return `[${label}](wiki:${encodeURIComponent(slug)})`;
  });
}

export function renderMarkdown(text: string): string {
  return md.render(preprocessWikilinks(text));
}

// Turn rendered `wiki:` links into clickable wikilinks; flag dangling targets.
// They route through the single `data-nav` dispatcher (see main.ts), which gives
// feedback when a target page doesn't exist rather than failing silently.
export function decorateWikilinks(root: ParentNode = content): void {
  root.querySelectorAll<HTMLAnchorElement>('a[href^="wiki:"]').forEach((a) => {
    const slug = decodeURIComponent(a.getAttribute("href")!.slice(5));
    a.classList.add("wikilink");
    a.dataset.slug = slug;
    a.dataset.nav = "page:" + slug;
    if (!state.slugSet.has(slug)) a.classList.add("dangling");
  });
}

export function animateIn(): void {
  content.classList.remove("view-enter");
  void content.offsetWidth; // force reflow so the CSS animation replays
  content.classList.add("view-enter");
}

export function mount(html: string): void {
  content.innerHTML = html;
  decorateWikilinks();
  animateIn();
}
