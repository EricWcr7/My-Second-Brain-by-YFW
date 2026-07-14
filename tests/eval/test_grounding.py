"""Grounding eval — measures the answer pipeline's citation-grounding accuracy.

Unlike the unit tests, this is an *eval*: a small golden set of cases run through
the real ``query.answer`` pipeline (with a faked model that returns a scripted
answer), scoring how reliably the grounding check flags **exactly** the invented
``[[slug]]`` citations and nothing else. Run with ``make eval``.

It needs no API key — the model is faked (``tests/fakes.py``). Extend ``GOLDEN`` as
the wiki's grounding behavior grows; the aggregate test asserts a perfect score
because the check is deterministic, so any regression fails loudly here.
"""

from __future__ import annotations

import pytest

from llmwiki.query import answer
from llmwiki.store import write_page
from llmwiki.wiki import concept_path

from tests.fakes import FakeProvider

# Each case: the pages that exist in the wiki, the model's scripted answer, and the
# slugs we expect the grounding check to flag as ungrounded (invented).
GOLDEN: list[dict] = [
    {
        "name": "all-grounded",
        "pages": ["Retrieval Practice"],
        "answer": "Retrieval practice strengthens recall. [[retrieval-practice]]",
        "expect_ungrounded": [],
    },
    {
        "name": "one-invented",
        "pages": ["Retrieval Practice"],
        "answer": "See [[retrieval-practice]] and also [[made-up-page]].",
        "expect_ungrounded": ["made-up-page"],
    },
    {
        "name": "alias-is-grounded",
        "pages": ["Retrieval Practice"],
        "answer": "Recall [[retrieval-practice|the practice]].",
        "expect_ungrounded": [],
    },
    {
        "name": "heading-anchor-is-grounded",
        "pages": ["Retrieval Practice"],
        "answer": "As in [[retrieval-practice#practice]].",
        "expect_ungrounded": [],
    },
    {
        "name": "no-citations-is-clean",
        "pages": ["Retrieval Practice"],
        "answer": "The pages don't cover this question.",
        "expect_ungrounded": [],
    },
    {
        "name": "all-invented",
        "pages": ["Retrieval Practice"],
        "answer": "See [[phantom-a]] and [[phantom-b]].",
        "expect_ungrounded": ["phantom-a", "phantom-b"],
    },
]


def _run_case(vault, case: dict, *, rerank: bool = False) -> list[str]:
    """Materialize the case's pages, run the pipeline, return flagged slugs."""
    vault.rerank = rerank
    for title in case["pages"]:
        write_page(
            concept_path(vault, "projects/learning", title),
            {"title": title, "type": "concept", "section": "projects/learning", "sources": ["s1"]},
            f"Body of {title}.",
        )
    provider = FakeProvider(answer_text=case["answer"])
    result = answer(vault, provider, "eval question", section="projects/learning")
    return result.ungrounded


# Reranking changes retrieval order, never the grounding contract — so every golden
# case must flag exactly the same invented citations with the rerank pass on or off.
@pytest.mark.parametrize("rerank", [False, True], ids=["rerank-off", "rerank-on"])
@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: c["name"])
def test_grounding_case(vault, case, rerank):
    assert _run_case(vault, case, rerank=rerank) == case["expect_ungrounded"]


def test_grounding_accuracy(vault, capsys):
    """Aggregate score over the golden set; must be perfect (the check is exact)."""
    passed = sum(1 for case in GOLDEN if _run_case(vault, case) == case["expect_ungrounded"])
    score = passed / len(GOLDEN)
    with capsys.disabled():
        print(f"\n[grounding eval] {passed}/{len(GOLDEN)} cases — accuracy {score:.0%}")
    assert score == 1.0
