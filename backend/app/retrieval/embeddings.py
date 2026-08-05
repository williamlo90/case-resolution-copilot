from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite, sqrt
from typing import Protocol, cast

from openai import OpenAI

EMBEDDING_DIMENSIONS = 32
EMBEDDING_VERSION = "deterministic-hash-v1"


class EmbeddingProvider(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


class _EmbeddingDatum(Protocol):
    @property
    def embedding(self) -> Sequence[float]: ...


class _EmbeddingResponse(Protocol):
    @property
    def data(self) -> Sequence[_EmbeddingDatum]: ...


class _EmbeddingsEndpoint(Protocol):
    def create(
        self,
        *,
        input: str,
        model: str,
        dimensions: int,
        encoding_format: str,
    ) -> _EmbeddingResponse: ...


class _OpenAIEmbeddingClient(Protocol):
    @property
    def embeddings(self) -> _EmbeddingsEndpoint: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DeterministicEmbeddingProvider:
    version: str = EMBEDDING_VERSION
    dimensions: int = EMBEDDING_DIMENSIONS

    def embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = sha256(token.encode()).digest()
            values[int.from_bytes(digest[:2], "big") % self.dimensions] += (
                1.0 if digest[2] % 2 else -1.0
            )
        norm = sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        client: _OpenAIEmbeddingClient | None = None,
    ) -> None:
        self._model = model
        self._dimensions = EMBEDDING_DIMENSIONS
        self._version = (
            "openai-embedding-v1-d32-" + sha256(model.encode()).hexdigest()[:12]
        )
        self._client = client or cast(
            _OpenAIEmbeddingClient,
            OpenAI(
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=max_retries,
            ),
        )

    @property
    def version(self) -> str:
        return self._version

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            input=text,
            model=self._model,
            dimensions=self._dimensions,
            encoding_format="float",
        )
        if len(response.data) != 1:
            raise RuntimeError("Embedding provider returned an unexpected result count.")
        values = [float(value) for value in response.data[0].embedding]
        if len(values) != self._dimensions or not all(isfinite(value) for value in values):
            raise RuntimeError("Embedding provider returned an invalid vector.")
        return values

    def close(self) -> None:
        self._client.close()


DEFAULT_EMBEDDING_PROVIDER = DeterministicEmbeddingProvider()


def embed(text: str) -> list[float]:
    return DEFAULT_EMBEDDING_PROVIDER.embed(text)
