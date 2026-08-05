from datetime import UTC, datetime

from app.integrations.connection_seed import (
    deterministic_connection_seeds,
    runtime_connection_seeds,
)


def test_connection_seed_covers_every_executable_action_without_secrets() -> None:
    seeds = deterministic_connection_seeds(checked_at=datetime(2026, 7, 23, tzinfo=UTC))

    action_types = {action_type for seed in seeds for action_type in seed.action_types}
    assert action_types == {
        "reverse_duplicate_charge",
        "issue_refund",
        "start_verified_recovery",
        "apply_service_correction",
    }
    assert all(seed.adapter_key == "deterministic_demo" for seed in seeds)
    assert all(seed.credential_status.value == "demo" for seed in seeds)
    assert all(
        not {
            "api_key",
            "access_token",
            "password",
            "client_secret",
        }.intersection(seed.model_dump().keys())
        for seed in seeds
    )


def test_runtime_connection_seeds_keep_case_intake_and_actions_separate() -> None:
    seeds = runtime_connection_seeds(
        case_source_provider="signed_webhook",
        action_target_provider="signed_webhook",
        case_source_fingerprint="a" * 64,
        action_target_fingerprint="b" * 64,
        environment="production",
        checked_at=datetime(2026, 7, 28, tzinfo=UTC),
    )

    assert [seed.public_id for seed in seeds] == [
        "CN-WEBHOOK-INTAKE",
        "CN-WEBHOOK-ACTIONS",
    ]
    assert seeds[0].read_capabilities == ["receive_case"]
    assert seeds[0].write_capabilities == []
    assert seeds[1].adapter_key == "signed_webhook"
    assert seeds[1].environment.value == "production"
    assert seeds[1].health.value == "not_configured"
    assert seeds[0].runtime_config_fingerprint == "a" * 64
    assert seeds[1].runtime_config_fingerprint == "b" * 64
    assert all(seed.credential_status.value == "connected" for seed in seeds)
    assert all(
        not {
            "api_key",
            "access_token",
            "password",
            "client_secret",
        }.intersection(seed.model_dump().keys())
        for seed in seeds
    )
