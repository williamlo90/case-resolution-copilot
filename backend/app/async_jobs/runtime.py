from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from app.async_jobs.settings import AsyncJobSettings
from app.config import Settings
from app.persistence.database import Database
from app.persistence.policy_indexing import SqlAlchemyPolicyIndexUnitOfWorkFactory
from app.retrieval.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from app.retrieval.v2.embeddings import (
    deterministic_policy_embedding_provider,
    openai_policy_embedding_provider,
)
from app.runtime.inbox import InboxRuntime, build_inbox_runtime
from app.services.policy_indexing import PolicyIndexingService


@dataclass(frozen=True, slots=True)
class AsyncJobRuntime:
    inbox: InboxRuntime | None
    policy_indexing: PolicyIndexingService | None


@contextmanager
def build_async_job_runtime(
    settings: Settings,
    job_settings: AsyncJobSettings,
) -> Iterator[AsyncJobRuntime]:
    if settings.database_url is None:
        yield AsyncJobRuntime(inbox=None, policy_indexing=None)
        return
    database = Database(settings.database_url)
    lease_seconds = job_settings.lease_duration_seconds()
    inbox = build_inbox_runtime(
        database=database,
        settings=settings,
        sync_lease_seconds=lease_seconds,
    )
    close_provider: OpenAIEmbeddingProvider | None = None
    policy_indexing: PolicyIndexingService | None = None
    if settings.policy_indexing_enabled:
        provider, close_provider = _policy_embedding_provider(settings)
        policy_indexing = PolicyIndexingService(
            unit_of_work=SqlAlchemyPolicyIndexUnitOfWorkFactory(database),
            embedding_provider=provider,
            profile_key=settings.policy_v2_profile_key,
            job_limit=1,
            page_budget=settings.policy_embedding_batch_size,
            lease_seconds=lease_seconds,
        )
    try:
        yield AsyncJobRuntime(inbox=inbox, policy_indexing=policy_indexing)
    finally:
        if inbox is not None:
            inbox.close()
        if close_provider is not None:
            close_provider.close()
        database.dispose()


def _policy_embedding_provider(
    settings: Settings,
) -> tuple[EmbeddingProvider, OpenAIEmbeddingProvider | None]:
    if settings.policy_v2_embedding_provider == "deterministic":
        return deterministic_policy_embedding_provider(), None
    api_key = settings.openai_secret()
    if api_key is None:
        raise ValueError("OpenAI policy indexing requires an API key.")
    provider = openai_policy_embedding_provider(
        api_key=api_key,
        model=settings.openai_embedding_model,
        timeout_seconds=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    return provider, provider
