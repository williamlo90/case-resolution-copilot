"""Seed input-only fixtures into a named disposable DB; never execute primary attempts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.config import Settings
from app.evaluation.case_resolution_v2.models import Scenario
from app.evaluation.case_resolution_v2.storage import digest
from app.evaluation.phase4_scenario_runtime import case_from_input, target_from_input
from app.main import create_app
from app.operator_study.storage import StudyBase, insert, record
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import MembershipModel, OrganizationModel
from app.security.authentication import DETERMINISTIC_ACTORS, DeterministicAuthProvider
from scripts.capture_phase4_run import _publish, _seed_baseline


def bootstrap(database_url: str, primary: Path, practice: Path, owner_subject: str) -> None:
    if not (make_url(database_url).database or "").startswith("operator_study_"):
        raise ValueError("Only a named disposable operator_study_ database is permitted")
    if not owner_subject.startswith("user_"):
        raise ValueError("Provide the verified existing Clerk operator subject")
    os.environ["SUPPORT_COPILOT_DATABASE_URL"] = database_url
    os.environ["SUPPORT_COPILOT_OPERATOR_STUDY_ENABLED"] = "false"
    command.upgrade(Config("alembic.ini"), "head")
    db = Database(database_url)
    StudyBase.metadata.create_all(db.engine)
    with db.session() as session:
        if record(session, "session", "primary") is not None:
            raise FileExistsError("Study already initialized; primary data must not be reset")
        if session.scalar(select(OrganizationModel.id)) is not None:
            raise ValueError("Expected a fresh empty study database")
    _seed_baseline(db)
    with db.session() as session:
        organization = session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == "ORG-0001")
        )
        assert organization is not None
        session.add(
            MembershipModel(
                public_id="STUDY-OWNER",
                organization_id=organization.id,
                subject_id=owner_subject,
                name="Study operator",
                email="operator@example.test",
                role="administrator",
                status="active",
            )
        )
    product = create_app(
        Settings(
            environment="test",
            database_url=database_url,
            operator_study_enabled=False,
            model_provider="deterministic",
            embedding_provider="deterministic",
            _env_file=None,
        )
    )
    product.state.auth_provider = DeterministicAuthProvider(DETERMINISTIC_ACTORS)
    with TestClient(product) as client:
        for connection in ("CN-0001", "CN-0002"):
            response = client.post(
                f"/api/connections/{connection}/test",
                headers={"X-Actor-ID": "USR-0003"},
                json={"expected_version": 1},
            )
            response.raise_for_status()
        for packet, path in (("practice", practice), ("training", practice), ("primary", primary)):
            bundle: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            if bool(bundle.get("practice")) != (packet != "primary"):
                raise ValueError("Primary/practice packet identity mismatch")
            if packet == "training":
                bundle = json.loads(
                    json.dumps(bundle)
                    .replace("PRACTICE-", "TRAIN-")
                    .replace("practice-20261018", "training-20261022")
                )
            for source in bundle["cases"].values():
                scenario = Scenario.model_validate(source)
                with db.session() as session:
                    CaseRepository(session).seed_case(
                        organization_public_id=scenario.tenant_id,
                        command=case_from_input(scenario),
                        correlation_id="hosted-study-bootstrap",
                    )
                    for target, state in target_from_input(scenario).items():
                        insert(session, "target", target, state)
                _publish(client, scenario)
            with db.session() as session:
                insert(session, "packet", packet, bundle)
                insert(
                    session,
                    "session",
                    packet,
                    {
                        "index": 0,
                        "active": None,
                        "ready": packet != "primary",
                        "owner_subject": owner_subject,
                        "inputs_sha256": digest(bundle),
                        "packet": packet,
                        "base_revision": bundle["base_revision"],
                        "clock": "postgres-clock_timestamp",
                        "purpose": "human_primary" if packet == "primary" else "practice_only",
                    },
                )
    db.dispose()
    print(
        "Prepared 6 engineering practice, 6 operator training and 24 primary variants; "
        "no primary attempt executed."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--practice", required=True, type=Path)
    parser.add_argument("--owner-subject", required=True)
    args = parser.parse_args()
    url = os.environ.get("SUPPORT_COPILOT_DATABASE_URL", "")
    bootstrap(url, args.primary, args.practice, args.owner_subject)


if __name__ == "__main__":
    main()
