from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.domain.cases import CaseRisk
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.main import create_app
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import AuditEventModel, MembershipModel, OrganizationModel

SPECIALIST = {"X-Actor-ID": "USR-0001"}


def _seed_case_organizations(database: Database) -> None:
    source_cases = DeterministicCaseSourceSimulator().fetch_cases()
    with database.session() as session:
        primary = OrganizationModel(
            public_id="ORG-0001", name="Northstar Cloud", slug="northstar-cloud"
        )
        other = OrganizationModel(
            public_id="ORG-0002", name="Other Organization", slug="other-organization"
        )
        session.add_all([primary, other])
        session.flush()
        session.add(
            MembershipModel(
                public_id="USR-0001",
                organization_id=primary.id,
                subject_id="USR-0001",
                name="Maya Specialist",
                email="maya.specialist@example.com",
                role="specialist",
                status="active",
            )
        )
        repository = CaseRepository(session)
        for command in source_cases:
            repository.seed_case(
                organization_public_id="ORG-0001",
                command=command,
                correlation_id=f"test-seed:{command.public_id}",
            )
        other_case = source_cases[0].model_copy(
            update={
                "public_id": "CS-9001",
                "source_id": "other-source:case-9001",
                "external_reference": "OTHER-9001",
            }
        )
        repository.seed_case(
            organization_public_id="ORG-0002",
            command=other_case,
            correlation_id="test-seed:CS-9001",
        )


def _extend_primary_queue_past_one_hundred(database: Database) -> None:
    template = DeterministicCaseSourceSimulator().fetch_cases()[0]
    with database.session() as session:
        repository = CaseRepository(session)
        for index in range(118):
            public_id = f"CS-Q{index:04d}"
            repository.seed_case(
                organization_public_id="ORG-0001",
                command=template.model_copy(
                    update={
                        "public_id": public_id,
                        "source_id": f"queue-test:{index:04d}",
                        "external_reference": f"QUEUE-{index:04d}",
                        "business_contexts": [
                            context.model_copy(
                                update={
                                    "public_id": f"CTX-{public_id}-{context_index:02d}",
                                    "source_reference": (f"{context.source_reference}:{public_id}"),
                                }
                            )
                            for context_index, context in enumerate(template.business_contexts)
                        ],
                    }
                ),
                correlation_id=f"test-seed:{public_id}",
            )


def _insert_case_before_active_cursor(database: Database) -> None:
    template = DeterministicCaseSourceSimulator().fetch_cases()[0]
    with database.session() as session:
        CaseRepository(session).seed_case(
            organization_public_id="ORG-0001",
            command=template.model_copy(
                update={
                    "public_id": "CS-0000",
                    "source_id": "queue-test:inserted-before-cursor",
                    "external_reference": "QUEUE-INSERTED",
                    "risk": CaseRisk.HIGH,
                    "due_at": datetime(2020, 1, 1, tzinfo=UTC),
                    "business_contexts": [
                        context.model_copy(
                            update={
                                "public_id": f"CTX-CS-0000-{context_index:02d}",
                                "source_reference": (f"{context.source_reference}:CS-0000"),
                            }
                        )
                        for context_index, context in enumerate(template.business_contexts)
                    ],
                }
            ),
            correlation_id="test-seed:CS-0000",
        )


def test_case_queue_reaches_and_searches_records_after_the_first_hundred(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_case_organizations(database)
    _extend_primary_queue_past_one_hundred(database)
    app = create_app(Settings(environment="test", database_url=test_database_url, _env_file=None))
    cursor: str | None = None
    seen: set[str] = set()
    offsets: list[int] = []
    first_page_ids: list[str] = []
    backward_checked = False

    with TestClient(app) as client:
        while True:
            parameters = {"limit": "8", "view": "all", "sort": "priority"}
            if cursor is not None:
                parameters["cursor"] = cursor
            response = client.get("/api/cases", headers=SPECIALIST, params=parameters)
            assert response.status_code == 200
            payload = response.json()
            assert payload["summary_scope"] == "organization"
            offsets.append(payload["offset"])
            page_ids = [item["id"] for item in payload["items"]]
            seen.update(page_ids)
            if not first_page_ids:
                first_page_ids = page_ids
                _insert_case_before_active_cursor(database)
            elif not backward_checked:
                previous = client.get(
                    "/api/cases",
                    headers=SPECIALIST,
                    params={
                        "limit": "8",
                        "view": "all",
                        "sort": "priority",
                        "cursor": payload["previous_cursor"],
                    },
                )
                assert previous.status_code == 200
                assert [item["id"] for item in previous.json()["items"]] == first_page_ids
                backward_checked = True
            cursor = payload["next_cursor"]
            if cursor is None:
                break

        searched = client.get(
            "/api/cases",
            headers=SPECIALIST,
            params={"query": "CS-Q0117", "limit": 8},
        )

    assert len(seen) == 121
    assert "CS-0000" not in seen
    assert backward_checked
    assert max(offsets) >= 104
    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["id"] == "CS-Q0117"


def test_generic_case_workflow_is_tenant_scoped_and_versioned(
    database: Database, test_database_url: str
) -> None:
    _seed_case_organizations(database)
    app = create_app(Settings(environment="test", database_url=test_database_url, _env_file=None))

    with TestClient(app) as client:
        listed = client.get(
            "/api/cases",
            headers={**SPECIALIST, "X-Organization-ID": "ORG-0002"},
        )
        hidden = client.get("/api/cases/CS-9001", headers=SPECIALIST)
        assigned = client.post(
            "/api/cases/CS-2048/assign",
            headers=SPECIALIST,
            json={"expected_version": 1},
        )
        stale = client.post(
            "/api/cases/CS-2048/assign",
            headers=SPECIALIST,
            json={"expected_version": 1},
        )
        noted = client.post(
            "/api/cases/CS-2048/notes",
            headers=SPECIALIST,
            json={"expected_case_version": 2, "body": "Verified customer identity."},
        )
        evidence_added = client.post(
            "/api/cases/CS-2048/evidence-records",
            headers=SPECIALIST,
            json={
                "expected_case_version": 3,
                "type": "payment",
                "label": "Settlement confirmation",
                "source": "Billing system",
                "source_reference": "PAY-SETTLEMENT-2048",
                "status": "settled",
                "fields": {"amount": "49.00", "currency": "USD"},
            },
        )
        evidence_replayed = client.post(
            "/api/cases/CS-2048/evidence-records",
            headers=SPECIALIST,
            json={
                "expected_case_version": 3,
                "type": "payment",
                "label": "Settlement confirmation",
                "source": "Billing system",
                "source_reference": "PAY-SETTLEMENT-2048",
                "status": "settled",
                "fields": {"amount": "49.00", "currency": "USD"},
            },
        )
        drafted = client.post(
            "/api/cases/CS-2048/draft",
            headers=SPECIALIST,
            json={
                "expected_version": 1,
                "subject": "Billing review update",
                "body": "We are reviewing the duplicate charge.",
            },
        )
        transitioned = client.post(
            "/api/cases/CS-2048/status",
            headers=SPECIALIST,
            json={"expected_version": 4, "status": "investigating"},
        )
        information_needed = client.post(
            "/api/cases/CS-2048/status",
            headers=SPECIALIST,
            json={"expected_version": 5, "status": "information_needed"},
        )
        resumed = client.post(
            "/api/cases/CS-2048/status",
            headers=SPECIALIST,
            json={"expected_version": 6, "status": "investigating"},
        )
        conversation = client.get("/api/cases/CS-2048/conversation", headers=SPECIALIST)

    assert listed.status_code == 200
    assert listed.json()["total"] == 3
    assert {item["id"] for item in listed.json()["items"]} == {
        "CS-2046",
        "CS-2047",
        "CS-2048",
    }
    assert hidden.status_code == 404
    assert assigned.status_code == 200
    assert assigned.json()["data"]["case"]["owner"]["id"] == "USR-0001"
    assert assigned.json()["data"]["case"]["version"] == 2
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    assert stale.json()["error"]["details"] == {
        "expected_version": 1,
        "current_version": 2,
    }
    assert noted.status_code == 200
    assert evidence_added.status_code == 200
    assert evidence_replayed.status_code == 200
    assert evidence_replayed.json()["data"]["case"]["version"] == 4
    assert evidence_added.json()["data"]["case"]["version"] == 4
    assert any(
        context["source_reference"] == "PAY-SETTLEMENT-2048"
        for context in evidence_added.json()["data"]["business_contexts"]
    )
    assert drafted.status_code == 200
    assert drafted.json()["data"]["response_draft"]["version"] == 2
    assert transitioned.status_code == 200
    assert transitioned.json()["data"]["case"]["status"] == "investigating"
    assert transitioned.json()["data"]["case"]["version"] == 5
    assert "request_information" in transitioned.json()["data"]["available_commands"]
    assert information_needed.status_code == 200
    assert information_needed.json()["data"]["case"]["status"] == "information_needed"
    assert "resume_investigation" in information_needed.json()["data"]["available_commands"]
    assert "request_information" not in information_needed.json()["data"]["available_commands"]
    assert resumed.status_code == 200
    assert resumed.json()["data"]["case"]["status"] == "investigating"
    assert conversation.status_code == 200
    assert conversation.json()["data"]["messages"][-1]["internal"] is True

    with database.session() as session:
        note_event = session.scalar(
            select(AuditEventModel).where(AuditEventModel.event_type == "case.note_added")
        )
        assert note_event is not None
        assert note_event.actor_id == "USR-0001"
        assert "body" not in note_event.data
        evidence_event = session.scalar(
            select(AuditEventModel).where(
                AuditEventModel.event_type == "case.evidence_added"
            )
        )
        assert evidence_event is not None
        assert evidence_event.actor_id == "USR-0001"
        assert "source_reference" not in evidence_event.data
