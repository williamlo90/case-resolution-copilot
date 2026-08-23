from app.retrieval.embeddings import (
    DeterministicEmbeddingProvider,
    OpenAIEmbeddingProvider,
)

POLICY_V2_DIMENSIONS = 512
DETERMINISTIC_POLICY_PROFILE = "deterministic-hash-v2-d512"
OPENAI_POLICY_MODEL = "text-embedding-3-small"
OPENAI_POLICY_PROFILE = "openai-text-embedding-3-small-v2-d512"


def deterministic_policy_embedding_provider() -> DeterministicEmbeddingProvider:
    return DeterministicEmbeddingProvider(
        version=DETERMINISTIC_POLICY_PROFILE,
        dimensions=POLICY_V2_DIMENSIONS,
    )


def openai_policy_embedding_provider(
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
    max_retries: int,
) -> OpenAIEmbeddingProvider:
    if model != OPENAI_POLICY_MODEL:
        raise ValueError(
            f"Policy profile {OPENAI_POLICY_PROFILE} requires {OPENAI_POLICY_MODEL}."
        )
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        dimensions=POLICY_V2_DIMENSIONS,
        version=OPENAI_POLICY_PROFILE,
    )
