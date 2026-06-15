"""Lint pass: deterministic structural checks plus an optional LLM review."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from . import prompts
from .config import Config
from .providers.base import LLMProvider
from .store import read_page
from .wiki import PageRef, extract_wikilinks, iter_pages, read_optional, section_contains


@dataclass
class LintIssue:
    level: str  # "error" | "warning" | "info"
    page: str
    message: str


class LintFindings(BaseModel):
    contradictions: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    stale_or_unclear: list[str] = Field(default_factory=list)
    missing_cross_references: list[str] = Field(default_factory=list)
    new_questions: list[str] = Field(default_factory=list)
    sources_to_seek: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


def _clean_slug(value: str) -> str:
    return value.strip().strip("[]").split("|", 1)[0].split("#", 1)[0].strip()


def _deterministic(config: Config, concepts: list[PageRef], sources: list[PageRef]):
    issues: list[LintIssue] = []
    all_slugs = {r.slug for r in concepts} | {r.slug for r in sources}
    source_slugs = {r.slug for r in sources}
    inbound = {r.slug: 0 for r in concepts}

    for ref in concepts + sources:
        page = read_page(ref.path)
        if page is None:
            continue
        if ref.page_type == "concept":
            srcs = page.metadata.get("sources") or []
            if not srcs:
                issues.append(
                    LintIssue("error", ref.slug, "concept page has no `sources` provenance")
                )
            else:
                for s in srcs:
                    slug = _clean_slug(str(s))
                    if slug and slug not in source_slugs:
                        issues.append(
                            LintIssue(
                                "warning",
                                ref.slug,
                                f"sources entry '{slug}' has no matching source page",
                            )
                        )
        for link in extract_wikilinks(page.content):
            if link in inbound:
                inbound[link] += 1
            if link not in all_slugs:
                issues.append(
                    LintIssue("warning", ref.slug, f"dangling wikilink [[{link}]]")
                )

    for slug, count in inbound.items():
        if count == 0:
            issues.append(
                LintIssue("info", slug, "orphan concept page (no inbound links)")
            )
    return issues


def _deep(config: Config, provider: LLMProvider, concepts: list[PageRef]):
    blocks: list[str] = []
    total = 0
    for ref in concepts:
        page = read_page(ref.path)
        if page is None:
            continue
        block = f"### [[{ref.slug}]] {ref.title}\n{page.content}"
        tokens = max(1, len(block) // 4)
        if total + tokens > config.context_token_budget and blocks:
            break
        blocks.append(block)
        total += tokens

    system = "\n\n".join(
        p for p in (prompts.load("lint.md"), read_optional(config.purpose_file)) if p.strip()
    ).strip()
    user = "Wiki pages:\n\n" + "\n\n".join(blocks)
    findings = provider.parse(system, user, LintFindings)

    issues: list[LintIssue] = []
    for item in findings.contradictions:
        issues.append(LintIssue("warning", "(review)", f"contradiction: {item}"))
    for item in findings.missing_concepts:
        issues.append(LintIssue("info", "(review)", f"missing concept: {item}"))
    for item in findings.stale_or_unclear:
        issues.append(LintIssue("info", "(review)", f"stale/unclear: {item}"))
    for item in findings.missing_cross_references:
        issues.append(LintIssue("info", "(review)", f"missing cross-reference: {item}"))
    for item in findings.new_questions:
        issues.append(LintIssue("info", "(review)", f"question to investigate: {item}"))
    for item in findings.sources_to_seek:
        issues.append(LintIssue("info", "(review)", f"source to seek: {item}"))
    for item in findings.data_gaps:
        issues.append(LintIssue("info", "(review)", f"data gap (web search): {item}"))
    return issues


def lint(
    config: Config,
    *,
    provider: LLMProvider | None = None,
    deep: bool = False,
    section: str | None = None,
) -> list[LintIssue]:
    concepts = iter_pages(config, "concept")
    sources = iter_pages(config, "source")
    if section:
        concepts = [r for r in concepts if section_contains(section, r.section)]
        sources = [r for r in sources if section_contains(section, r.section)]

    issues = _deterministic(config, concepts, sources)
    if deep and provider is not None and concepts:
        issues += _deep(config, provider, concepts)
    return issues
