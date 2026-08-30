import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.analysis.ai_assisted_decision_engine import OpenAIAssistedDecisionEngine
from app.analysis.deterministic_decision_engine import (
    DecisionEngine,
    DeterministicDecisionEngine,
)
from app.api.errors import register_error_handlers
from app.api.middleware import (
    CORRELATION_HEADER,
    SERVER_TIMING_HEADER,
    SUPPORT_TIMING_HEADER,
    register_http_middleware,
)
from app.api.routes.actions import router as actions_router
from app.api.routes.audit import router as audit_router
from app.api.routes.case_intake import router as case_intake_router
from app.api.routes.cases import router as cases_router
from app.api.routes.connections import router as connections_router
from app.api.routes.decision_briefs import router as decision_briefs_router
from app.api.routes.health import create_health_router
from app.api.routes.inbox_connections import router as inbox_connections_router
from app.api.routes.inbox_drafts import router as inbox_drafts_router
from app.api.routes.inbox_internal import router as inbox_internal_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.policies import router as policies_router
from app.api.routes.policy_index_internal import router as policy_index_internal_router
from app.api.routes.quality import router as quality_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.session import router as session_router
from app.api.routes.settings import router as settings_router
from app.config import Settings, get_settings
from app.integrations.action_gateway import (
    ActionGateway,
    DeterministicActionGateway,
    RoutingActionGateway,
)
from app.integrations.clerk_identity import ClerkIdentityGateway
from app.integrations.connection_activation import activate_runtime_connections
from app.integrations.webhook_action_gateway import SignedWebhookActionGateway
from app.logging import configure_logging
from app.models.openai_decision import OpenAIDecisionNarrativeGateway
from app.orchestrators.langgraph_orchestrator import LangGraphDecisionOrchestrator
from app.persistence.database import Database
from app.persistence.policy_indexing import SqlAlchemyPolicyIndexUnitOfWorkFactory
from app.retrieval.embeddings import (
    DEFAULT_EMBEDDING_PROVIDER,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.retrieval.v2.embeddings import (
    deterministic_policy_embedding_provider,
    openai_policy_embedding_provider,
)
from app.runtime.inbox import build_inbox_runtime
from app.security.authentication import (
    AuthProvider,
    ClerkAuthProvider,
    ClerkSessionVerifier,
    DatabaseActorResolver,
    DatabaseInvitationProvisioner,
    DeterministicAuthProvider,
    UnavailableProviderAuth,
)
from app.services.policy_indexing import PolicyIndexingService


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings)
    logger = logging.getLogger(__name__)
    database = Database(runtime_settings.database_url) if runtime_settings.database_url else None
    baseline_decision_engine = DeterministicDecisionEngine()
    openai_gateway: OpenAIDecisionNarrativeGateway | None = None
    openai_embedding_provider: OpenAIEmbeddingProvider | None = None
    openai_policy_v2_provider: OpenAIEmbeddingProvider | None = None
    webhook_action_gateway: SignedWebhookActionGateway | None = None
    decision_engine: DecisionEngine = baseline_decision_engine
    embedding_provider: EmbeddingProvider = DEFAULT_EMBEDDING_PROVIDER
    policy_v2_embedding_provider: EmbeddingProvider = deterministic_policy_embedding_provider()
    inbox_runtime = build_inbox_runtime(database=database, settings=runtime_settings)
    if runtime_settings.model_provider == "openai":
        openai_api_key = runtime_settings.openai_secret()
        assert openai_api_key is not None
        openai_gateway = OpenAIDecisionNarrativeGateway(
            api_key=openai_api_key,
            model=runtime_settings.openai_model,
            timeout_seconds=runtime_settings.openai_timeout_seconds,
            max_retries=runtime_settings.openai_max_retries,
        )
        decision_engine = OpenAIAssistedDecisionEngine(
            baseline=baseline_decision_engine,
            narrative_gateway=openai_gateway,
        )
    decision_engine = LangGraphDecisionOrchestrator(decision_engine)
    if runtime_settings.embedding_provider == "openai":
        openai_api_key = runtime_settings.openai_secret()
        assert openai_api_key is not None
        openai_embedding_provider = OpenAIEmbeddingProvider(
            api_key=openai_api_key,
            model=runtime_settings.openai_embedding_model,
            timeout_seconds=runtime_settings.openai_timeout_seconds,
            max_retries=runtime_settings.openai_max_retries,
        )
        embedding_provider = openai_embedding_provider
    if runtime_settings.policy_v2_embedding_provider == "openai":
        openai_api_key = runtime_settings.openai_secret()
        assert openai_api_key is not None
        openai_policy_v2_provider = openai_policy_embedding_provider(
            api_key=openai_api_key,
            model=runtime_settings.openai_embedding_model,
            timeout_seconds=runtime_settings.openai_timeout_seconds,
            max_retries=runtime_settings.openai_max_retries,
        )
        policy_v2_embedding_provider = openai_policy_v2_provider
    policy_indexing_service = (
        PolicyIndexingService(
            unit_of_work=SqlAlchemyPolicyIndexUnitOfWorkFactory(database),
            embedding_provider=policy_v2_embedding_provider,
            profile_key=runtime_settings.policy_v2_profile_key,
            job_limit=runtime_settings.policy_index_job_limit,
            page_budget=runtime_settings.policy_embedding_batch_size,
        )
        if database is not None and runtime_settings.policy_indexing_enabled
        else None
    )
    secret_key = runtime_settings.clerk_secret()
    jwt_key = runtime_settings.clerk_public_key()
    auth_provider: AuthProvider
    invitation_gateway: ClerkIdentityGateway | None = None
    if runtime_settings.auth_mode == "deterministic_development":
        auth_provider = DeterministicAuthProvider()
    elif (
        database is not None
        and runtime_settings.clerk_auth_configured()
        and secret_key is not None
        and jwt_key is not None
    ):
        invitation_gateway = ClerkIdentityGateway(
            secret_key=secret_key,
            invitation_redirect_url=runtime_settings.clerk_invitation_redirect_url(),
        )
        auth_provider = ClerkAuthProvider(
            verifier=ClerkSessionVerifier(
                jwt_key=jwt_key,
                authorized_parties=runtime_settings.allowed_clerk_parties(),
            ),
            resolver=DatabaseActorResolver(database),
            provisioner=DatabaseInvitationProvisioner(
                database=database,
                directory=invitation_gateway,
            ),
        )
    else:
        auth_provider = UnavailableProviderAuth()
    deterministic_action_gateway = DeterministicActionGateway()
    action_gateway: ActionGateway = deterministic_action_gateway
    if runtime_settings.action_target_provider == "signed_webhook":
        action_webhook_url = runtime_settings.action_webhook_url
        action_webhook_secret = runtime_settings.action_webhook_secret_value()
        assert action_webhook_url is not None
        assert action_webhook_secret is not None
        webhook_action_gateway = SignedWebhookActionGateway(
            url=action_webhook_url,
            secret=action_webhook_secret,
            timeout_seconds=runtime_settings.action_webhook_timeout_seconds,
        )
        action_gateway = RoutingActionGateway(
            {
                "deterministic_demo": deterministic_action_gateway,
                "signed_webhook": webhook_action_gateway,
            }
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("application_started", extra=runtime_settings.safe_log_context())
        try:
            if database:
                try:
                    activated_connections = activate_runtime_connections(
                        database=database,
                        settings=runtime_settings,
                    )
                    if activated_connections:
                        logger.info(
                            "runtime_connections_activated",
                            extra={"connection_count": len(activated_connections)},
                        )
                except SQLAlchemyError:
                    logger.error("runtime_connection_activation_database_unavailable")
            yield
        finally:
            if webhook_action_gateway:
                webhook_action_gateway.close()
            if openai_gateway:
                openai_gateway.close()
            if openai_embedding_provider:
                openai_embedding_provider.close()
            if openai_policy_v2_provider:
                openai_policy_v2_provider.close()
            if invitation_gateway:
                invitation_gateway.close()
            if inbox_runtime:
                inbox_runtime.close()
            if database:
                database.dispose()
        logger.info("application_stopped", extra={"service": runtime_settings.service_name})

    app = FastAPI(
        title="Case Resolution Copilot API",
        version="1.0.0-pilot",
        lifespan=lifespan,
        docs_url=None if runtime_settings.environment == "production" else "/docs",
        redoc_url=None if runtime_settings.environment == "production" else "/redoc",
        openapi_url=None if runtime_settings.environment == "production" else "/openapi.json",
    )
    register_http_middleware(
        app,
        production=runtime_settings.environment == "production",
    )
    cors_headers = ["Authorization", "Content-Type", CORRELATION_HEADER]
    if runtime_settings.auth_mode == "deterministic_development":
        cors_headers.extend(["X-Actor-ID", "X-Actor-Role"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.allowed_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=cors_headers,
        expose_headers=[
            CORRELATION_HEADER,
            SERVER_TIMING_HEADER,
            SUPPORT_TIMING_HEADER,
        ],
    )
    register_error_handlers(app)
    app.state.database = database
    app.state.auth_provider = auth_provider
    app.state.invitation_gateway = invitation_gateway
    app.state.settings = runtime_settings
    app.state.decision_engine = decision_engine
    app.state.embedding_provider = embedding_provider
    app.state.policy_v2_embedding_provider = policy_v2_embedding_provider
    app.state.policy_indexing_service = policy_indexing_service
    app.state.action_gateway = action_gateway
    app.state.inbox_runtime = inbox_runtime
    app.include_router(
        create_health_router(
            runtime_settings.service_name,
            database_check=database.is_ready if database else None,
            source_revision=_source_revision(),
        )
    )
    app.include_router(case_intake_router)
    app.include_router(cases_router)
    app.include_router(decision_briefs_router)
    app.include_router(session_router)
    app.include_router(organizations_router)
    app.include_router(policies_router)
    app.include_router(policy_index_internal_router)
    app.include_router(reviews_router)
    app.include_router(actions_router)
    app.include_router(connections_router)
    app.include_router(inbox_connections_router)
    app.include_router(inbox_drafts_router)
    app.include_router(inbox_internal_router)
    app.include_router(quality_router)
    app.include_router(notifications_router)
    app.include_router(settings_router)
    app.include_router(audit_router)
    return app


def _source_revision() -> str | None:
    value = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


app = create_app()
