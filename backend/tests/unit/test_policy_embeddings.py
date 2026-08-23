import pytest

from app.retrieval.embeddings import (
    EMBEDDING_DIMENSIONS,
    OpenAIEmbeddingProvider,
    embed,
)
from app.retrieval.v2.embeddings import openai_policy_embedding_provider


class _EmbeddingDatum:
    def __init__(self, values: list[float]) -> None:
        self.embedding = values


class _EmbeddingResponse:
    def __init__(self, values: list[float]) -> None:
        self.data = [_EmbeddingDatum(values)]


class _EmbeddingsEndpoint:
    def __init__(self, values: list[float]) -> None:
        self.values = values
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        *,
        input: str,
        model: str,
        dimensions: int,
        encoding_format: str,
    ) -> _EmbeddingResponse:
        self.calls.append(
            {
                "input": input,
                "model": model,
                "dimensions": dimensions,
                "encoding_format": encoding_format,
            }
        )
        return _EmbeddingResponse(self.values)


class _EmbeddingClient:
    def __init__(self, values: list[float]) -> None:
        self.embeddings = _EmbeddingsEndpoint(values)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_embedding_is_deterministic_normalized_and_fixed_size() -> None:
    first = embed("duplicate plan charge service credit")
    second = embed("duplicate plan charge service credit")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_unrelated_queries_do_not_share_identical_vectors() -> None:
    assert embed("billing service credit") != embed("account access recovery")


def test_openai_embedding_provider_is_configured_and_validates_dimensions() -> None:
    client = _EmbeddingClient([0.125] * EMBEDDING_DIMENSIONS)
    provider = OpenAIEmbeddingProvider(
        api_key="not-used-by-injected-client",
        model="text-embedding-3-small",
        timeout_seconds=5,
        max_retries=1,
        client=client,
    )

    result = provider.embed("A disputed invoice needs review.")
    provider.close()

    assert result == [0.125] * EMBEDDING_DIMENSIONS
    assert provider.dimensions == EMBEDDING_DIMENSIONS
    assert provider.version.startswith("openai-embedding-v1-d32-")
    assert client.embeddings.calls == [
        {
            "input": "A disputed invoice needs review.",
            "model": "text-embedding-3-small",
            "dimensions": EMBEDDING_DIMENSIONS,
            "encoding_format": "float",
        }
    ]
    assert client.closed


def test_openai_embedding_provider_rejects_invalid_vectors() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="not-used-by-injected-client",
        model="text-embedding-3-small",
        timeout_seconds=5,
        max_retries=1,
        client=_EmbeddingClient([0.125] * (EMBEDDING_DIMENSIONS - 1)),
    )

    with pytest.raises(RuntimeError, match="invalid vector"):
        provider.embed("A disputed invoice needs review.")


def test_openai_policy_profile_rejects_model_identity_drift() -> None:
    with pytest.raises(ValueError, match="requires text-embedding-3-small"):
        openai_policy_embedding_provider(
            api_key="not-used",
            model="text-embedding-3-large",
            timeout_seconds=5,
            max_retries=0,
        )
