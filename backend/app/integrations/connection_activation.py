from app.config import Settings
from app.integrations.connection_seed import runtime_connection_seeds
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database


def activate_runtime_connections(
    *,
    database: Database,
    settings: Settings,
) -> list[str]:
    organization_id = settings.integration_organization_id
    seeds = runtime_connection_seeds(
        case_source_provider=settings.case_source_provider,
        action_target_provider=settings.action_target_provider,
        case_source_fingerprint=settings.case_webhook_configuration_fingerprint(),
        action_target_fingerprint=settings.action_webhook_configuration_fingerprint(),
        environment=settings.environment,
    )
    if organization_id is None and seeds:
        raise ValueError("Integration organization is required.")
    if organization_id is None:
        return []
    with database.session() as session:
        repository = ConnectionRepository(session)
        repository.lock_runtime_configuration()
        activated = (
            [
                repository.synchronize_runtime(
                    organization_public_id=organization_id,
                    command=seed,
                    correlation_id=f"runtime-connection:{seed.public_id}",
                ).public_id
                for seed in seeds
            ]
            if organization_id is not None
            else []
        )
        repository.deactivate_runtime(
            active_organization_public_id=organization_id,
            active_connection_ids=set(activated),
            correlation_id="runtime-connection:deactivate",
        )
        return activated
