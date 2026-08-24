import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.cases import CaseCreate, CaseWorkspaceRecord
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import ConversationMessageModel, ConversationThreadModel
from app.persistence.policy_repository import PolicyRepository

ORGANIZATION_PUBLIC_ID = "ORG-0001"
FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "evidence"
    / "developer-workflow-benchmark"
    / "product-fixtures"
)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURE_DIRECTORY.glob("*.json"))


def _require_safe_configuration(
    *,
    database_url: str | None,
    environment: str,
    acknowledged: bool,
) -> None:
    if environment == "production":
        raise RuntimeError("Benchmark seeding is disabled in production.")
    if not acknowledged:
        raise RuntimeError(
            "Set SUPPORT_COPILOT_ALLOW_BENCHMARK_SEED=1 to acknowledge synthetic data seeding."
        )
    if not database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required.")


def _load_fixture(path: Path) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if payload.get("condition") != "copilot":
        raise RuntimeError(f"{path.name} is not a Copilot-condition fixture.")
    return payload


def _require_policies(repository: PolicyRepository, policy_ids: list[str]) -> None:
    missing = [
        policy_id
        for policy_id in policy_ids
        if repository.get_workspace(
            organization_public_id=ORGANIZATION_PUBLIC_ID,
            policy_public_id=policy_id,
        )
        is None
    ]
    if missing:
        raise RuntimeError(f"Seed governed policies first; missing: {', '.join(missing)}")


def _seed_messages(
    *,
    session: Session,
    workspace: CaseWorkspaceRecord,
    messages: list[dict[str, Any]],
) -> int:
    added = 0
    for message in messages[1:]:
        existing = session.scalar(
            select(ConversationMessageModel.id).where(
                ConversationMessageModel.organization_id == workspace.case.organization_id,
                ConversationMessageModel.public_id == message["public_id"],
            )
        )
        if existing is not None:
            continue
        session.add(
            ConversationMessageModel(
                public_id=message["public_id"],
                organization_id=workspace.case.organization_id,
                case_id=workspace.case.id,
                thread_id=workspace.thread.id,
                author_type=message["author_type"],
                author_id=message["author_id"],
                author_name=message["author_name"],
                channel=message["channel"],
                body=message["body"],
                internal=message["internal"],
                source_reference=message["source_reference"],
                version=1,
                created_at=_parse_datetime(message["created_at"]),
            )
        )
        added += 1
    if added:
        thread = session.get(ConversationThreadModel, workspace.thread.id)
        if thread is None:
            raise RuntimeError(f"Conversation thread missing for {workspace.case.public_id}.")
        thread.version += added
        thread.updated_at = max(_parse_datetime(item["created_at"]) for item in messages)
        session.flush()
    return added


def seed_benchmark_fixtures(
    *,
    database_url: str | None,
    environment: str,
    acknowledged: bool,
) -> None:
    _require_safe_configuration(
        database_url=database_url,
        environment=environment,
        acknowledged=acknowledged,
    )
    paths = _fixture_paths()
    if len(paths) != 3:
        raise RuntimeError(f"Expected exactly three product fixtures, found {len(paths)}.")

    database = Database(database_url or "")
    created = 0
    messages_added = 0
    try:
        with database.session() as session:
            case_repository = CaseRepository(session)
            policy_repository = PolicyRepository(session)
            for path in paths:
                payload = _load_fixture(path)
                command = CaseCreate.model_validate(payload["case"])
                _require_policies(policy_repository, list(payload["policy_ids"]))
                workspace, was_created = case_repository.seed_case_with_status(
                    organization_public_id=ORGANIZATION_PUBLIC_ID,
                    command=command,
                    correlation_id=f"benchmark-seed:{command.public_id}",
                )
                created += int(was_created)
                messages_added += _seed_messages(
                    session=session,
                    workspace=workspace,
                    messages=list(payload["conversation"]),
                )
        print(
            f"Benchmark fixtures present: {len(paths)}; created: {created}; "
            f"conversation messages added: {messages_added}."
        )
    finally:
        database.dispose()


def main() -> None:
    settings = Settings()
    seed_benchmark_fixtures(
        database_url=settings.database_url,
        environment=settings.environment,
        acknowledged=os.getenv("SUPPORT_COPILOT_ALLOW_BENCHMARK_SEED") == "1",
    )


if __name__ == "__main__":
    main()
