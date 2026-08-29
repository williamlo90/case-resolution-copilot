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
    }
    for name in ("ecs-worker-task-definition.json", "ecs-scheduler-task-definition.json"):
        container = _template(name)["containerDefinitions"][0]
        environment = {item["name"]: item["value"] for item in container["environment"]}
        assert required.items() <= environment.items()
