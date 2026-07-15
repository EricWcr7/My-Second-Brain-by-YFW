import math
from types import SimpleNamespace

import pytest

from llmwiki.embeddings import Embedder, validate_embedding_vectors
from llmwiki.providers import ProviderError


@pytest.mark.parametrize(
    ("vectors", "expected", "message"),
    [
        ([], 1, "returned 0 vectors for 1 chunks"),
        ([[1.0, 2.0], [1.0]], 2, "inconsistent dimensions"),
        ([[]], 1, "empty vectors"),
        ([[1.0, math.nan]], 1, "non-finite values"),
        ([[1.0, "not-a-number"]], 1, "non-numeric vector values"),
    ],
)
def test_validate_embedding_vectors_rejects_malformed_responses(
    vectors, expected, message
):
    with pytest.raises(ProviderError, match=message):
        validate_embedding_vectors(vectors, expected, unit="chunks")


def test_embedder_rejects_duplicate_response_indexes():
    response = SimpleNamespace(
        data=[
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
            SimpleNamespace(index=0, embedding=[0.0, 1.0]),
        ],
        usage=None,
    )
    embedder = object.__new__(Embedder)
    embedder.client = SimpleNamespace(
        embeddings=SimpleNamespace(create=lambda **kwargs: response)
    )
    embedder._openai = SimpleNamespace(OpenAIError=Exception)

    with pytest.raises(ProviderError, match="invalid item indexes"):
        embedder.embed(["one", "two"], model="test-model")
