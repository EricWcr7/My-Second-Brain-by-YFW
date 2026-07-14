"""A fake LLM provider so the pipelines can be tested without API calls."""

from __future__ import annotations

import math
import re
from pathlib import Path

from llmwiki.ingest import (
    ConceptDraft,
    GenerationResult,
    SourceAnalysis,
    SourcePageDraft,
)
from llmwiki.lint import LintFindings
from llmwiki.providers.base import LLMProvider
from llmwiki.rerank import RerankResult


class FakeProvider(LLMProvider):
    def __init__(
        self,
        *,
        analysis: SourceAnalysis | None = None,
        generation: GenerationResult | None = None,
        answer_text: str = "Fake answer [[concept]].",
        findings: LintFindings | None = None,
        rerank_order: list[str] | None = None,
    ):
        self._analysis = analysis
        self._generation = generation
        self._answer = answer_text
        self._findings = findings
        self._rerank_order = rerank_order
        self.calls: list[str] = []

    def with_timeout(self, timeout: float) -> "FakeProvider":
        # Record the requested timeout so a test can assert ingest scopes its own;
        # no real client to rescope, so return self unchanged.
        self.calls.append(f"with_timeout:{timeout}")
        return self

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
        if schema is RerankResult:
            # Empty by default → rerank_hits keeps the retrieval order unchanged.
            return RerankResult(slugs=self._rerank_order or [])
        raise AssertionError(f"unexpected schema {schema!r}")

    def transcribe_pdf(self, path: Path) -> str:
        self.calls.append("transcribe_pdf")
        return "# PDF\n\nTranscribed PDF content with $x^2$."

    def transcribe_image(self, path: Path) -> str:
        self.calls.append("transcribe_image")
        return "Transcribed image content."

    def count_tokens(self, system, user, *, model=None) -> int:
        return max(1, len(user) // 4)


class FakeEmbedder:
    """Deterministic bag-of-words embedder for tests (no network, no key).

    Each text becomes an L2-normalized count vector over a small fixed vocabulary
    (prefix-matched, so ``reviews`` hits ``review``), plus a constant
    baseline dimension so a vector is never all-zero. Texts sharing vocabulary get
    high cosine similarity, which is enough to assert hybrid ranking deterministically.
    """

    DEFAULT_VOCAB = (
        "retrieval", "practice", "recall", "memory", "review", "spaced",
        "repetition", "feedback", "learning", "schedule", "sunset", "sky",
    )

    def __init__(self, vocab: tuple[str, ...] = DEFAULT_VOCAB):
        self.vocab = list(vocab)
        self.calls: list[tuple[str, int]] = []

    @property
    def available(self) -> bool:
        return True

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        self.calls.append((model, len(texts)))
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        words = re.findall(r"[a-z]+", text.lower())
        counts = [float(sum(w.startswith(v) for w in words)) for v in self.vocab]
        counts.append(0.1)  # baseline keeps the vector non-zero for cosine
        norm = math.sqrt(sum(x * x for x in counts)) or 1.0
        return [x / norm for x in counts]
