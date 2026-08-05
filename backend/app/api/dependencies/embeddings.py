from typing import cast

from fastapi import Request

from app.retrieval.embeddings import (
    DEFAULT_EMBEDDING_PROVIDER,
    EmbeddingProvider,
)


def configured_embedding_provider(request: Request) -> EmbeddingProvider:
    return cast(
        EmbeddingProvider,
        getattr(
            request.app.state,
            "embedding_provider",
            DEFAULT_EMBEDDING_PROVIDER,
        ),
    )
