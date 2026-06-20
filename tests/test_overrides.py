"""Per-section override resolution and how it reaches the pipelines."""

from __future__ import annotations

import pytest

from llmwiki import overrides
from llmwiki.query import answer
from llmwiki.store import write_page
from llmwiki.wiki import concept_path

from tests.fakes import FakeProvider


def test_fresh_vault_inherits_general(vault):
    for component in overrides.COMPONENTS:
        assert overrides.read_override(vault, "academic/calc", component) is None
        assert overrides.effective(vault, "academic/calc", component) == overrides.general_default(
            vault, component
        )
    assert set(overrides.override_status(vault, "academic/calc").values()) == {"general"}


def test_write_read_delete_section_override(vault):
    overrides.write_override(vault, "academic/calc", "answer", "CUSTOM ANSWER")
    assert overrides.is_overridden(vault, "academic/calc", "answer")
    assert overrides.read_override(vault, "academic/calc", "answer") == "CUSTOM ANSWER"
    assert overrides.effective(vault, "academic/calc", "answer") == "CUSTOM ANSWER"
    # A sibling section is unaffected — resolution is general-default-only, no
    # walking up ancestors.
    assert overrides.effective(vault, "non-academic", "answer") == overrides.general_default(
        vault, "answer"
    )
    assert overrides.sections_with_overrides(vault) == {"academic/calc"}

    assert overrides.delete_override(vault, "academic/calc", "answer") is True
    assert overrides.read_override(vault, "academic/calc", "answer") is None
    assert overrides.sections_with_overrides(vault) == set()


def test_general_baseline_edit_affects_all_sections(vault):
    # Editing the General root rewrites the general op-prompt baseline that every
    # uncustomized section inherits.
    overrides.write_override(vault, "", "answer", "BASELINE")
    assert overrides.general_default(vault, "answer") == "BASELINE"
    assert overrides.effective(vault, "academic/calc", "answer") == "BASELINE"
    # Resetting an op baseline re-exposes the packaged default.
    assert overrides.delete_override(vault, "", "answer") is True
    assert overrides.general_default(vault, "answer") != "BASELINE"


def test_general_purpose_schema_have_no_reset(vault):
    # purpose/schema baselines ARE the wiki files; there is nothing to reset to.
    assert overrides.delete_override(vault, "", "purpose") is False
    assert overrides.delete_override(vault, "", "schema") is False


def test_purpose_general_default_is_wiki_file(vault):
    assert overrides.general_default(vault, "purpose") == vault.purpose_file.read_text("utf-8")


def test_unknown_component_raises(vault):
    with pytest.raises(ValueError):
        overrides.write_override(vault, "academic/calc", "nope", "x")


def test_override_reaches_answer_system_prompt(vault):
    write_page(
        concept_path(vault, "academic/calc", "Gradient"),
        {"title": "Gradient", "type": "concept", "section": "academic/calc", "sources": ["s1"]},
        "gradient content",
    )
    overrides.write_override(vault, "academic/calc", "answer", "MARKER-ANSWER-PROMPT")

    captured: dict[str, str] = {}

    class CapturingProvider(FakeProvider):
        def complete(self, system, user, *, model=None, max_tokens=16000):
            captured["system"] = system
            return super().complete(system, user, model=model, max_tokens=max_tokens)

    provider = CapturingProvider(answer_text="see [[gradient]]")
    answer(vault, provider, "explain gradient", section="academic/calc")
    assert "MARKER-ANSWER-PROMPT" in captured["system"]
    # A different section falls back to the general answer prompt.
    answer(vault, provider, "explain gradient", section="non-academic")
    assert "MARKER-ANSWER-PROMPT" not in captured["system"]
