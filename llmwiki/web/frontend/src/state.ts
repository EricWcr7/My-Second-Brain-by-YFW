// Shared app types and mutable state. `slugSet` is reassigned when pages load,
// so other modules must always read it through this object (not capture it).

export interface Meta {
  sections: string[];
  concept_count: number;
  source_count: number;
  default_section?: string;
  has_api_key: boolean;
  api_key_env: string;
  supported_exts?: string[];
}

export interface PageRef {
  slug: string;
  title: string;
  section: string;
  type: string;
}

export interface LintIssue {
  level: string;
  page: string;
  message: string;
}

export interface QueryResult {
  answer: string;
  pages_used: string[];
}

export interface IngestResult {
  status: string; // "ingested" | "skipped"
  title: string;
  source_slug: string | null;
  concept_slugs: string[];
  reason: string;
  warnings: string[];
  section: string;
}

export const state = {
  meta: {
    sections: [],
    concept_count: 0,
    source_count: 0,
    has_api_key: false,
    api_key_env: "OPENAI_API_KEY",
  } as Meta,
  pages: [] as PageRef[],
  slugSet: new Set<string>(),
  // Current scope driving Ask/Search/Lint. "" = General (whole knowledge base).
  scope: "",
};
