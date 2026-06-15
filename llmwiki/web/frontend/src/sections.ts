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

// Short label for a node: its last segment; "" -> "General".
export function sectionLabel(section: string): string {
  const segs = sectionSegments(section);
  return segs.length ? segs[segs.length - 1] : "General";
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
