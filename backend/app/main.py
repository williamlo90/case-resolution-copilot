from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.api.routes.cases import router as cases_router
from app.api.routes.connections import router as connections_router
from app.api.routes.decision_briefs import router as decision_briefs_router
from app.api.routes.health import create_health_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.policies import router as policies_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.session import router as session_router
from app.config import Settings, get_settings
from app.integrations.action_gateway import (
    ActionGateway,
    DeterministicActionGateway,
)
from app.integrations.clerk_identity import ClerkIdentityGateway
from app.models.openai_decision import OpenAIDecisionNarrativeGateway
from app.persistence.database import Database
from app.retrieval.embeddings import (
    DEFAULT_EMBEDDING_PROVIDER,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.security.authentication import (
    AuthProvider,
    ClerkAuthProvider,
    ClerkSessionVerifier,
    DatabaseActorResolver,
    DatabaseInvitationProvisioner,
    DeterministicAuthProvider,
    UnavailableProviderAuth,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    database = (
        Database(runtime_settings.database_url)
        if runtime_settings.database_url
        else None
    )
    baseline_decision_engine = DeterministicDecisionEngine()
    decision_engine: DecisionEngine = baseline_decision_engine
    embedding_provider: EmbeddingProvider = DEFAULT_EMBEDDING_PROVIDER
    openai_gateway: OpenAIDecisionNarrativeGateway | None = None
    openai_embedding_provider: OpenAIEmbeddingProvider | None = None
    action_gateway: ActionGateway = DeterministicActionGateway()
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
    invitation_gateway: ClerkIdentityGateway | None = None
    secret_key = runtime_settings.clerk_secret()
    jwt_key = runtime_settings.clerk_public_key()

    auth_provider: AuthProvider
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

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if openai_gateway:
                openai_gateway.close()
            if openai_embedding_provider:
                openai_embedding_provider.close()
            if invitation_gateway:
                invitation_gateway.close()
            if database:
                database.dispose()

    application = FastAPI(
        title="Case Resolution Copilot API",
        version="0.3.0",
        lifespan=lifespan,
        docs_url=None if runtime_settings.environment == "production" else "/docs",
        redoc_url=None if runtime_settings.environment == "production" else "/redoc",
        openapi_url=(
            None if runtime_settings.environment == "production" else "/openapi.json"
        ),
    )
    register_http_middleware(
        application,
        production=runtime_settings.environment == "production",
    )
    cors_headers = ["Authorization", "Content-Type", CORRELATION_HEADER]
    if runtime_settings.auth_mode == "deterministic_development":
        cors_headers.extend(["X-Actor-ID", "X-Actor-Role"])
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.allowed_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=cors_headers,
        expose_headers=[
            CORRELATION_HEADER,
            SERVER_TIMING_HEADER,
            SUPPORT_TIMING_HEADER,
        ],
    )
    register_error_handlers(application)
    application.state.database = database
    application.state.auth_provider = auth_provider
    application.state.invitation_gateway = invitation_gateway
    application.state.settings = runtime_settings
    application.state.decision_engine = decision_engine
    application.state.embedding_provider = embedding_provider
    application.state.action_gateway = action_gateway
    application.include_router(
        create_health_router(
            runtime_settings.service_name,
            database_check=database.is_ready if database else None,
        )
    )
    application.include_router(session_router)
    application.include_router(organizations_router)
    application.include_router(cases_router)
    application.include_router(policies_router)
    application.include_router(decision_briefs_router)
    application.include_router(reviews_router)
    application.include_router(actions_router)
    application.include_router(connections_router)
    return application


app = create_app()
