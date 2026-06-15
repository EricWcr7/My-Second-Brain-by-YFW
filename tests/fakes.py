"""A fake LLM provider so the pipelines can be tested without API calls."""

from __future__ import annotations

from pathlib import Path

from llmwiki.ingest import (
    ConceptDraft,
    GenerationResult,
    SourceAnalysis,
    SourcePageDraft,
)
from llmwiki.lint import LintFindings
from llmwiki.providers.base import LLMProvider


class FakeProvider(LLMProvider):
    def __init__(
        self,
        *,
        analysis: SourceAnalysis | None = None,
        generation: GenerationResult | None = None,
        answer_text: str = "Fake answer [[concept]].",
        findings: LintFindings | None = None,
    ):
        self._analysis = analysis
        self._generation = generation
        self._answer = answer_text
        self._findings = findings
        self.calls: list[str] = []

    def complete(self, system, user, *, model=None, max_tokens=16000) -> str:
        self.calls.append("complete")
        return self._answer

    def parse(self, system, user, schema, *, model=None, max_tokens=16000):
        self.calls.append(f"parse:{schema.__name__}")
        if schema is SourceAnalysis:
            assert self._analysis is not None
            return self._analysis
        if schema is GenerationResult:
            assert self._generation is not None
            return self._generation
        if schema is LintFindings:
            return self._findings or LintFindings()
        raise AssertionError(f"unexpected schema {schema!r}")

    def transcribe_pdf(self, path: Path) -> str:
        self.calls.append("transcribe_pdf")
        return "# PDF\n\nTranscribed PDF content with $x^2$."

    def transcribe_image(self, path: Path) -> str:
        self.calls.append("transcribe_image")
        return "Transcribed image content."

    def count_tokens(self, system, user, *, model=None) -> int:
        return max(1, len(user) // 4)
