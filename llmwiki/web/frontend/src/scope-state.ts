import { scopeNodes } from "./sections";
import { state } from "./state";

export const SCOPE_STORAGE_KEY = "llmwiki.scope";

function knownScopes(): Set<string> {
  return new Set(scopeNodes(["academic", ...state.meta.sections]));
}

export function isKnownScope(scope: string): boolean {
  return knownScopes().has(scope);
}

export function restoreScope(): string {
  let saved = "";
  try {
    saved = localStorage.getItem(SCOPE_STORAGE_KEY) || "";
  } catch {
    saved = "";
  }
  state.scope = isKnownScope(saved) ? saved : "";
  persistScope(state.scope);
  return state.scope;
}

export function setActiveScope(scope: string, persist = true): string {
  state.scope = isKnownScope(scope) ? scope : "";
  if (persist) persistScope(state.scope);
  return state.scope;
}

function persistScope(scope: string): void {
  try {
    localStorage.setItem(SCOPE_STORAGE_KEY, scope);
  } catch {
    // Storage can be unavailable in hardened browser profiles. In-memory scope
    // still works for the active session.
  }
}
