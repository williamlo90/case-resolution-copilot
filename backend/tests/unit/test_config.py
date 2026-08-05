import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.api_port == 8000
    assert settings.safe_log_context() == {
        "service": "support-copilot-api",
        "environment": "development",
        "auth_mode": "deterministic_development",
        "model_provider": "deterministic",
        "embedding_provider": "deterministic",
        "openai_model": "gpt-5.6-luna",
        "openai_embedding_model": "text-embedding-3-small",
        "log_level": "INFO",
        "api_host": "127.0.0.1",
        "api_port": 8000,
        "case_source_provider": "disabled",
        "action_target_provider": "deterministic",
    }


def test_support_copilot_environment_prefix_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPPORT_COPILOT_SERVICE_NAME", "support-test-api")
    monkeypatch.setenv("SUPPORT_COPILOT_API_PORT", "8123")

    settings = Settings(_env_file=None)

    assert settings.service_name == "support-test-api"
    assert settings.api_port == 8123


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "staging"),
        ("auth_mode", "trusted_header"),
        ("log_level", "VERBOSE"),
        ("api_port", 0),
        ("api_port", 65536),
    ],
)
def test_invalid_configuration_fails_explicitly(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})  # type: ignore[arg-type]


def test_production_rejects_deterministic_development_auth() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)

    settings = Settings(
        environment="production",
        auth_mode="provider",
        database_url="postgresql+psycopg://example.invalid/support_copilot",
        clerk_secret_key="sk_placeholder",
        clerk_jwt_key=("-----BEGIN PUBLIC KEY-----\\nplaceholder\\n-----END PUBLIC KEY-----"),
        clerk_authorized_parties="https://app.example.com",
        _env_file=None,
    )
    assert settings.auth_mode == "provider"


@pytest.mark.parametrize(
    "configuration",
    [
        {},
        {"database_url": "postgresql+psycopg://example.invalid/support_copilot"},
        {
            "database_url": "postgresql+psycopg://example.invalid/support_copilot",
            "clerk_secret_key": "sk_placeholder",
        },
    ],
)
def test_production_requires_complete_provider_configuration(
    configuration: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="provider",
            _env_file=None,
            **configuration,  # type: ignore[arg-type]
        )


def test_clerk_configuration_normalizes_pem_and_authorized_parties() -> None:
    settings = Settings(
        clerk_secret_key="sk_placeholder",
        clerk_jwt_key=("-----BEGIN PUBLIC KEY-----\\nplaceholder\\n-----END PUBLIC KEY-----"),
        clerk_authorized_parties="https://app.example.com, https://admin.example.com ",
        _env_file=None,
    )

    assert settings.clerk_auth_configured()
    assert settings.clerk_public_key() == (
        "-----BEGIN PUBLIC KEY-----\nplaceholder\n-----END PUBLIC KEY-----"
    )
    assert settings.allowed_clerk_parties() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert (
        settings.clerk_invitation_redirect_url()
        == "https://app.example.com/invite"
    )


def test_production_rejects_local_clerk_authorized_parties() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="provider",
            database_url="postgresql+psycopg://example.invalid/support_copilot",
            clerk_secret_key="sk_placeholder",
            clerk_jwt_key=("-----BEGIN PUBLIC KEY-----\\nplaceholder\\n-----END PUBLIC KEY-----"),
            _env_file=None,
        )


def test_openai_provider_requires_a_key_without_exposing_it_to_logs() -> None:
    with pytest.raises(ValidationError):
        Settings(model_provider="openai", _env_file=None)

    settings = Settings(
        model_provider="openai",
        openai_api_key="sk-test-placeholder",
        _env_file=None,
    )

    assert settings.openai_secret() == "sk-test-placeholder"
    assert settings.safe_log_context()["model_provider"] == "openai"
    assert "openai_api_key" not in settings.safe_log_context()


def test_openai_embedding_provider_requires_a_key_and_records_only_safe_config() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_provider="openai", _env_file=None)

    settings = Settings(
        embedding_provider="openai",
        openai_api_key="sk-test-placeholder",
        openai_embedding_model="text-embedding-3-small",
        _env_file=None,
    )

    assert settings.safe_log_context()["embedding_provider"] == "openai"
    assert settings.safe_log_context()["openai_embedding_model"] == (
        "text-embedding-3-small"
    )
    assert "openai_api_key" not in settings.safe_log_context()


def test_signed_webhooks_require_complete_strong_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(
            case_source_provider="signed_webhook",
            integration_organization_id="ORG-0001",
            case_webhook_secret="too-short",
            _env_file=None,
        )
    with pytest.raises(ValidationError):
        Settings(
            action_target_provider="signed_webhook",
            integration_organization_id="ORG-0001",
            action_webhook_url="https://actions.example.com/hooks",
            _env_file=None,
        )

    settings = Settings(
        case_source_provider="signed_webhook",
        action_target_provider="signed_webhook",
        integration_organization_id="ORG-0001",
        case_webhook_secret="case-secret-with-at-least-32-characters",
        action_webhook_url="https://actions.example.com/hooks",
        action_webhook_secret="action-secret-with-at-least-32-characters",
        _env_file=None,
    )

    assert settings.case_webhook_configured()
    assert settings.action_webhook_configured()
    case_fingerprint = settings.case_webhook_configuration_fingerprint()
    action_fingerprint = settings.action_webhook_configuration_fingerprint()
    assert case_fingerprint is not None and len(case_fingerprint) == 64
    assert action_fingerprint is not None and len(action_fingerprint) == 64
    assert case_fingerprint != action_fingerprint
    assert "case-secret" not in case_fingerprint
    assert "action-secret" not in action_fingerprint
    assert "case_webhook_secret" not in settings.safe_log_context()
    assert "action_webhook_secret" not in settings.safe_log_context()


def test_production_rejects_insecure_action_webhook_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="provider",
            database_url="postgresql+psycopg://example.invalid/support_copilot",
            clerk_secret_key="sk_placeholder",
            clerk_jwt_key=("-----BEGIN PUBLIC KEY-----\\nplaceholder\\n-----END PUBLIC KEY-----"),
            clerk_authorized_parties="https://app.example.com",
            action_target_provider="signed_webhook",
            integration_organization_id="ORG-0001",
            action_webhook_url="http://actions.example.com/hooks",
            action_webhook_secret="action-secret-with-at-least-32-characters",
            _env_file=None,
        )
