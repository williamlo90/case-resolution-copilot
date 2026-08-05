from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import (
    CORRELATION_HEADER,
    SERVER_TIMING_HEADER,
    SUPPORT_TIMING_HEADER,
    register_http_middleware,
)
from app.api.routes.health import create_health_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.session import router as session_router
from app.config import Settings, get_settings
from app.integrations.clerk_identity import ClerkIdentityGateway
from app.persistence.database import Database
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
            if invitation_gateway:
                invitation_gateway.close()
            if database:
                database.dispose()

    application = FastAPI(
        title="Case Resolution Copilot API",
        version="0.2.0",
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
    application.include_router(
        create_health_router(
            runtime_settings.service_name,
            database_check=database.is_ready if database else None,
        )
    )
    application.include_router(session_router)
    application.include_router(organizations_router)
    return application


app = create_app()
