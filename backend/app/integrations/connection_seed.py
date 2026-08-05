from datetime import UTC, datetime

from app.domain.connections import (
    ConnectionEnvironment,
    ConnectionHealth,
    ConnectionSeed,
    CredentialStatus,
)


def deterministic_connection_seeds(
    *,
    checked_at: datetime | None = None,
) -> list[ConnectionSeed]:
    timestamp = checked_at or datetime.now(UTC)
    return [
        ConnectionSeed(
            public_id="CN-0001",
            name="Billing operations demo",
            provider_type="billing",
            adapter_key="deterministic_demo",
            environment=ConnectionEnvironment.DEMO,
            health=ConnectionHealth.HEALTHY,
            credential_status=CredentialStatus.DEMO,
            read_capabilities=["lookup_transaction", "lookup_refund"],
            write_capabilities=[
                "reverse_duplicate_charge",
                "issue_refund",
            ],
            action_types=[
                "reverse_duplicate_charge",
                "issue_refund",
            ],
            affected_work=["billing_dispute", "refund_request"],
            last_checked_at=timestamp,
        ),
        ConnectionSeed(
            public_id="CN-0002",
            name="Identity operations demo",
            provider_type="identity",
            adapter_key="deterministic_demo",
            environment=ConnectionEnvironment.DEMO,
            health=ConnectionHealth.HEALTHY,
            credential_status=CredentialStatus.DEMO,
            read_capabilities=["lookup_account"],
            write_capabilities=["start_verified_recovery"],
            action_types=["start_verified_recovery"],
            affected_work=["account_access"],
            last_checked_at=timestamp,
        ),
        ConnectionSeed(
            public_id="CN-0003",
            name="Service operations demo",
            provider_type="service_operations",
            adapter_key="deterministic_demo",
            environment=ConnectionEnvironment.DEMO,
            health=ConnectionHealth.HEALTHY,
            credential_status=CredentialStatus.DEMO,
            read_capabilities=["lookup_service_order"],
            write_capabilities=["apply_service_correction"],
            action_types=["apply_service_correction"],
            affected_work=["service_exception"],
            last_checked_at=timestamp,
        ),
    ]


def runtime_connection_seeds(
    *,
    case_source_provider: str,
    action_target_provider: str,
    case_source_fingerprint: str | None,
    action_target_fingerprint: str | None,
    environment: str,
    checked_at: datetime | None = None,
) -> list[ConnectionSeed]:
    timestamp = checked_at or datetime.now(UTC)
    target_environment = (
        ConnectionEnvironment.PRODUCTION
        if environment == "production"
        else ConnectionEnvironment.SANDBOX
    )
    seeds: list[ConnectionSeed] = []
    if case_source_provider == "signed_webhook":
        if case_source_fingerprint is None:
            raise ValueError("The case source configuration fingerprint is required.")
        seeds.append(
            ConnectionSeed(
                public_id="CN-WEBHOOK-INTAKE",
                name="Case intake webhook",
                provider_type="case_source",
                adapter_key="signed_webhook",
                environment=target_environment,
                health=ConnectionHealth.HEALTHY,
                credential_status=CredentialStatus.CONNECTED,
                read_capabilities=["receive_case"],
                write_capabilities=[],
                action_types=[],
                affected_work=[
                    "billing_dispute",
                    "refund_request",
                    "account_access",
                    "service_exception",
                ],
                last_checked_at=timestamp,
                runtime_config_fingerprint=case_source_fingerprint,
            )
        )
    if action_target_provider == "signed_webhook":
        if action_target_fingerprint is None:
            raise ValueError("The action target configuration fingerprint is required.")
        seeds.append(
            ConnectionSeed(
                public_id="CN-WEBHOOK-ACTIONS",
                name="Controlled action webhook",
                provider_type="business_operations",
                adapter_key="signed_webhook",
                environment=target_environment,
                health=ConnectionHealth.NOT_CONFIGURED,
                credential_status=CredentialStatus.CONNECTED,
                read_capabilities=["check_action_outcome"],
                write_capabilities=[
                    "reverse_duplicate_charge",
                    "issue_refund",
                    "start_verified_recovery",
                    "apply_service_correction",
                ],
                action_types=[
                    "reverse_duplicate_charge",
                    "issue_refund",
                    "start_verified_recovery",
                    "apply_service_correction",
                ],
                affected_work=[
                    "billing_dispute",
                    "refund_request",
                    "account_access",
                    "service_exception",
                ],
                last_checked_at=None,
                runtime_config_fingerprint=action_target_fingerprint,
            )
        )
    return seeds
