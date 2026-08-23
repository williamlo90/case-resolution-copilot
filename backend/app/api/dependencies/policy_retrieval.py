from typing import Protocol, cast

from fastapi import Request

from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.governed_facade import GovernedPolicyRetrievalFacade
from app.retrieval.v1_governed import PolicyEvidenceSearchStore, V1PolicyRetrieval
from app.retrieval.v2.embeddings import deterministic_policy_embedding_provider
from app.retrieval.v2.retriever import PolicyHybridRetrievalStore, V2PolicyRetrieval


class PolicyRetrievalStore(
    PolicyEvidenceSearchStore,
    PolicyHybridRetrievalStore,
    Protocol,
):
    pass


def configured_policy_retrieval(
    request: Request,
    *,
    store: PolicyRetrievalStore,
    v1_embedding_provider: EmbeddingProvider,
) -> GovernedPolicyRetrievalFacade:
    v1 = V1PolicyRetrieval(
        store=store,
        embedding_provider=v1_embedding_provider,
    )
    settings = getattr(request.app.state, "settings", None)
    if settings is None or settings.policy_retrieval_mode == "v1":
        return GovernedPolicyRetrievalFacade(v1=v1)
    v2_provider = cast(
        EmbeddingProvider,
        getattr(
            request.app.state,
            "policy_v2_embedding_provider",
            deterministic_policy_embedding_provider(),
        ),
    )
    return GovernedPolicyRetrievalFacade(
        v1=v1,
        v2=V2PolicyRetrieval(
            store=store,
            embedding_provider=v2_provider,
            profile_key=settings.policy_v2_profile_key,
            query_character_limit=settings.policy_query_char_limit,
        ),
        mode=settings.policy_retrieval_mode,
    )
