// Section-path helpers, mirroring llmwiki/wiki.py. A section is a `/`-joined
// path of slug segments; "" is the General root that sees the whole base.

export function sectionSegments(section: string): string[] {
  return (section || "").split("/").filter(Boolean);
}

// A scope sees a section iff the scope is a prefix of it (segment-boundary safe).
export function sectionContains(scope: string, section: string): boolean {
  if (!scope) return true;
  return section === scope || section.startsWith(scope + "/");
}

// Human-readable label for a node: its last segment, title-cased; "" -> "General".
// Display only — scope values/links still use the raw slug path.
export function sectionLabel(section: string): string {
  const segs = sectionSegments(section);
  if (!segs.length) return "General";
  return segs[segs.length - 1]
    .split("-")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

// Full-path label for pickers: "" -> "General", "projects/atlas" -> "Projects › Atlas".
export function sectionPathLabel(section: string): string {
  const segs = sectionSegments(section);
  if (!segs.length) return "General";
  return segs.map((seg) => sectionLabel(seg)).join(" › ");
}

// Selectable scope nodes for the tree: the General root, every section that has
// pages, and all their ancestors — sorted so parents precede children.
export function scopeNodes(sections: string[]): string[] {
  const set = new Set<string>([""]);
  for (const s of sections) {
    const segs = sectionSegments(s);
    for (let i = 1; i <= segs.length; i++) set.add(segs.slice(0, i).join("/"));
  }
  return [...set].sort();
}

// Immediate children of `scope` (one segment deeper) across the known sections.
export function childSections(scope: string, sections: string[]): string[] {
  const depth = sectionSegments(scope).length;
  return scopeNodes(sections)
    .filter((n) => n !== scope && sectionContains(scope, n) && sectionSegments(n).length === depth + 1)
    .sort();
}

// The prefix chain from the General root down to `scope`, e.g.
// "academic/calc" -> ["", "academic", "academic/calc"]. Drives the breadcrumb.
export function sectionAncestors(scope: string): string[] {
  const segs = sectionSegments(scope);
  const chain = [""];
  for (let i = 1; i <= segs.length; i++) chain.push(segs.slice(0, i).join("/"));
  return chain;
}
