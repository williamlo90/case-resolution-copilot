from functools import lru_cache
from hashlib import sha256
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated configuration with legacy support-copilot names kept for compatibility."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SUPPORT_COPILOT_",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "support-copilot-api"
    environment: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["deterministic_development", "provider"] = "deterministic_development"
    model_provider: Literal["deterministic", "openai"] = "deterministic"
    embedding_provider: Literal["deterministic", "openai"] = "deterministic"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str | None = None
    cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    clerk_secret_key: SecretStr | None = None
    clerk_jwt_key: SecretStr | None = None
    clerk_authorized_parties: str = "http://127.0.0.1:3000,http://localhost:3000"
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-5.6-luna", min_length=1, max_length=100)
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        min_length=1,
        max_length=100,
    )
    openai_timeout_seconds: float = Field(default=12, ge=1, le=60)
    openai_max_retries: int = Field(default=1, ge=0, le=2)
    case_source_provider: Literal["disabled", "signed_webhook"] = "disabled"
    action_target_provider: Literal["deterministic", "signed_webhook"] = "deterministic"
    integration_organization_id: str | None = Field(
        default=None,
        pattern=r"^ORG-[A-Z0-9-]+$",
        max_length=64,
    )
    case_webhook_secret: SecretStr | None = None
    case_webhook_max_age_seconds: int = Field(default=300, ge=60, le=900)
    action_webhook_url: str | None = Field(default=None, max_length=2000)
    action_webhook_secret: SecretStr | None = None
    action_webhook_timeout_seconds: float = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def reject_unsafe_production_modes(self) -> Self:
        if self.model_provider == "openai" and not self.openai_configured():
            raise ValueError("OpenAI model provider requires an API key")
        if self.embedding_provider == "openai" and not self.openai_configured():
            raise ValueError("OpenAI embedding provider requires an API key")
        if self.environment == "production" and self.auth_mode == "deterministic_development":
            raise ValueError("production requires provider authentication")
        if self.environment == "production" and self.auth_mode == "provider":
            if not self.database_url:
                raise ValueError("production provider authentication requires a database")
            if not self.clerk_auth_configured():
                raise ValueError("production provider authentication requires Clerk credentials")
            if any(not party.startswith("https://") for party in self.allowed_clerk_parties()):
                raise ValueError(
                    "production Clerk authorized parties must use explicit HTTPS origins"
                )
        if self.case_source_provider == "signed_webhook" and (
            not self.integration_organization_id or not self.case_webhook_configured()
        ):
            raise ValueError(
                "signed case webhook requires an organization and a strong signing secret"
            )
        if self.action_target_provider == "signed_webhook" and (
            not self.integration_organization_id or not self.action_webhook_configured()
        ):
            raise ValueError(
                "signed action webhook requires an organization, HTTPS URL, and signing secret"
            )
        if (
            self.environment == "production"
            and self.action_webhook_url
            and urlsplit(self.action_webhook_url).scheme != "https"
        ):
            raise ValueError("production action webhook URL must use HTTPS")
        return self

    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def allowed_clerk_parties(self) -> list[str]:
        return [
            party.strip() for party in self.clerk_authorized_parties.split(",") if party.strip()
        ]

    def clerk_auth_configured(self) -> bool:
        secret_key = self.clerk_secret()
        public_key = self.clerk_public_key()
        return bool(
            secret_key
            and secret_key.startswith("sk_")
            and public_key
            and "-----BEGIN PUBLIC KEY-----" in public_key
            and "-----END PUBLIC KEY-----" in public_key
            and self.allowed_clerk_parties()
        )

    def clerk_invitation_redirect_url(self) -> str:
        parties = self.allowed_clerk_parties()
        if not parties:
            raise ValueError("Clerk authorized parties are required")
        return f"{parties[0].rstrip('/')}/invite"

    def clerk_secret(self) -> str | None:
        return self.clerk_secret_key.get_secret_value() if self.clerk_secret_key else None

    def clerk_public_key(self) -> str | None:
        if self.clerk_jwt_key is None:
            return None
        return self.clerk_jwt_key.get_secret_value().replace("\\n", "\n")

    def openai_configured(self) -> bool:
        secret = self.openai_secret()
        return bool(secret and not secret.startswith("replace_"))

    def openai_secret(self) -> str | None:
        if self.openai_api_key is None:
            return None
        return self.openai_api_key.get_secret_value().strip()

    def case_webhook_configured(self) -> bool:
        return _usable_webhook_secret(self.case_webhook_secret_value())

    def case_webhook_secret_value(self) -> str | None:
        return _secret_value(self.case_webhook_secret)

    def action_webhook_configured(self) -> bool:
        secret = self.action_webhook_secret_value()
        if not _usable_webhook_secret(secret) or not self.action_webhook_url:
            return False
        parsed = urlsplit(self.action_webhook_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def action_webhook_secret_value(self) -> str | None:
        return _secret_value(self.action_webhook_secret)

    def case_webhook_configuration_fingerprint(self) -> str | None:
        secret = self.case_webhook_secret_value()
        if not self.case_webhook_configured() or secret is None:
            return None
        return _configuration_fingerprint(
            "case_webhook",
            secret,
            str(self.case_webhook_max_age_seconds),
        )

    def action_webhook_configuration_fingerprint(self) -> str | None:
        secret = self.action_webhook_secret_value()
        if not self.action_webhook_configured() or secret is None:
            return None
        return _configuration_fingerprint(
            "action_webhook",
            secret,
            self.action_webhook_url or "",
            str(self.action_webhook_timeout_seconds),
        )

    def safe_log_context(self) -> dict[str, str | int | bool]:
        return {
            "service": self.service_name,
            "environment": self.environment,
            "auth_mode": self.auth_mode,
            "model_provider": self.model_provider,
            "embedding_provider": self.embedding_provider,
            "openai_model": self.openai_model,
            "openai_embedding_model": self.openai_embedding_model,
            "log_level": self.log_level,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "case_source_provider": self.case_source_provider,
            "action_target_provider": self.action_target_provider,
        }


def _secret_value(value: SecretStr | None) -> str | None:
    return value.get_secret_value().strip() if value else None


def _usable_webhook_secret(value: str | None) -> bool:
    return bool(value and len(value) >= 32 and not value.lower().startswith("replace_"))


def _configuration_fingerprint(*values: str) -> str:
    return sha256("\0".join(values).encode("utf-8")).hexdigest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
