from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.domain.controlled_operations import OPERATIONS
from app.domain.resolution import VerificationState
from app.integrations.action_gateway import ActionGatewayError
from app.main import create_app
from app.operator_study.gateway import PersistentStudyGateway
from app.operator_study.storage import StudyBase, StudyRecord, insert, record
from app.persistence.database import Database
from tests.unit.test_controlled_target import gateway_request


def isolated_database(path: Path) -> Database:
    # Only the small study tables need SQLite; the hosted integration gate uses Neon.
    database = Database.__new__(Database)
    database.engine = create_engine(f"sqlite:///{path}")
    database._session_factory = sessionmaker(
        bind=database.engine, class_=Session, expire_on_commit=False
    )
    StudyBase.metadata.create_all(database.engine)
    return database


@pytest.mark.parametrize("operation", list(OPERATIONS))
def test_receipt_and_target_survive_instance_replacement(tmp_path: Path, operation: str) -> None:
    database = isolated_database(tmp_path / "study.db")
    request = gateway_request(operation)
    with database.session() as session:
        insert(
            session,
            "target",
            request.target,
            {
                "owner": "SYNTHETIC-OWNER-1",
                "invoice_state": "draft",
                "currency": "USD",
                "active_sessions": "3",
                "credited_minor": "0",
            },
        )
    args: dict[str, Any] = {
        "adapter_key": "deterministic_demo",
        "provider_type": OPERATIONS[operation].provider,
        "request": request,
    }
    receipt = PersistentStudyGateway(database).execute(**args)
    database.dispose()
    replacement = isolated_database(tmp_path / "study.db")
    gateway = PersistentStudyGateway(replacement)
    assert gateway.execute(**args).duplicate
    lookup = gateway.reconcile(**args, external_reference=receipt.external_reference)
    assert lookup.readback and lookup.readback.status == VerificationState.VERIFIED
    with replacement.session() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(StudyRecord).where(StudyRecord.kind == "effect")
            )
            == 1
        )
    replacement.dispose()


def test_durable_readback_detects_tampering_and_rejects_payload_rebinding(tmp_path: Path) -> None:
    database = isolated_database(tmp_path / "study.db")
    request = gateway_request("rename_account")
    with database.session() as session:
        insert(session, "target", request.target, {"owner": "SYNTHETIC-OWNER-1"})
    gateway = PersistentStudyGateway(database)
    args: dict[str, Any] = {
        "adapter_key": "deterministic_demo",
        "provider_type": "identity",
        "request": request,
    }
    assert gateway.reconcile(**args, external_reference=None).found is None
    gateway.execute(**args)
    with database.session() as session:
        target = record(session, "target", request.target)
        assert target is not None
        target.value = {**target.value, "new_name": "tampered"}
    lookup = PersistentStudyGateway(database).reconcile(**args, external_reference=None)
    assert lookup.readback and lookup.readback.status == VerificationState.MISMATCH
    assert lookup.readback.observed_parameters["new_name"] == "tampered"
    changed = request.model_copy(update={"parameters": {**request.parameters, "new_name": "other"}})
    with pytest.raises(ActionGatewayError, match="different payload"):
        gateway.execute(**{**args, "request": changed})
    database.dispose()


def test_study_endpoints_are_absent_by_default_and_production_flag_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(environment="test", _env_file=None)
    application = create_app(settings)
    assert not any("/operator-study" in getattr(route, "path", "") for route in application.routes)
    monkeypatch.setenv("VERCEL_ENV", "production")
    with pytest.raises(ValueError, match="disposable study database"):
        create_app(settings.model_copy(update={"operator_study_enabled": True}))
