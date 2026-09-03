import json
from pathlib import Path
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
AWS_ROOT = REPOSITORY_ROOT / "deploy" / "aws"


def _template(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((AWS_ROOT / name).read_text(encoding="utf-8")))


def test_scheduler_has_a_writable_tmp_volume_for_celery_beat() -> None:
    template = _template("ecs-scheduler-task-definition.json")
    container = template["containerDefinitions"][0]

    assert container["readonlyRootFilesystem"] is True
    assert template["volumes"] == [{"name": "scheduler-tmp"}]
    assert container["mountPoints"] == [
        {
            "sourceVolume": "scheduler-tmp",
            "containerPath": "/tmp",
            "readOnly": False,
        }
    ]
    assert "--schedule=/tmp/celerybeat-schedule" in container["command"]
    assert "--pidfile=/tmp/celerybeat.pid" in container["command"]


def test_worker_and_scheduler_enable_the_same_durable_capabilities() -> None:
    required = {
        "SUPPORT_COPILOT_INBOX_SCHEDULED_SYNC_ENABLED": "true",
        "SUPPORT_COPILOT_POLICY_INDEXING_ENABLED": "true",
        "SUPPORT_COPILOT_ASYNC_BROKER_URL": "sqs://",
    }
    for name in ("ecs-worker-task-definition.json", "ecs-scheduler-task-definition.json"):
        container = _template(name)["containerDefinitions"][0]
        environment = {item["name"]: item["value"] for item in container["environment"]}
        assert required.items() <= environment.items()


def test_api_enables_the_same_durable_capabilities() -> None:
    container = _template("ecs-api-task-definition.json")["containerDefinitions"][0]
    environment = {item["name"]: item["value"] for item in container["environment"]}

    assert environment["SUPPORT_COPILOT_INBOX_SCHEDULED_SYNC_ENABLED"] == "true"
    assert environment["SUPPORT_COPILOT_POLICY_INDEXING_ENABLED"] == "true"
    assert environment["SUPPORT_COPILOT_ASYNC_BROKER_URL"] == "sqs://"
    assert "/api/health/live" in container["healthCheck"]["command"][1]


def test_migration_has_the_minimum_valid_production_auth_contract() -> None:
    container = _template("ecs-migration-task-definition.json")["containerDefinitions"][0]
    environment = {item["name"]: item["value"] for item in container["environment"]}
    secrets = {item["name"] for item in container["secrets"]}

    assert environment["SUPPORT_COPILOT_AUTH_MODE"] == "provider"
    assert environment["SUPPORT_COPILOT_CLERK_AUTHORIZED_PARTIES"].startswith("REPLACE_")
    assert {
        "SUPPORT_COPILOT_DATABASE_URL",
        "SUPPORT_COPILOT_CLERK_SECRET_KEY",
        "SUPPORT_COPILOT_CLERK_JWT_KEY",
    } <= secrets


def test_container_contract_excludes_development_dependencies() -> None:
    containerfile = (REPOSITORY_ROOT / "backend" / "Containerfile").read_text(
        encoding="utf-8"
    )
    entrypoint = (REPOSITORY_ROOT / "backend" / "container-entrypoint.sh").read_text(
        encoding="utf-8"
    )

    assert containerfile.count("uv sync --frozen --no-dev") == 2
    assert "USER supportcopilot" in containerfile
    assert "sslmode=require" in entrypoint
    assert "unset SUPPORT_COPILOT_DB_USERNAME SUPPORT_COPILOT_DB_PASSWORD" in entrypoint
    assert "SUPPORT_COPILOT_REDIS_AUTH_TOKEN" in entrypoint
    assert 'scheme = "rediss"' in entrypoint
    assert "unset SUPPORT_COPILOT_REDIS_AUTH_TOKEN" in entrypoint
