from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from app.config import Settings
from app.domain.cases import CaseCategory, CaseRisk, CaseUrgency
from app.domain.identity import ActorContext
from app.domain.inbox import InboxAuthorizationError, InboxConflict
from app.domain.inbox.external import SelectedThreadImportCommand
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import AuditEventModel, MembershipModel, OrganizationModel
from app.runtime.inbox import build_inbox_runtime
from app.security.authentication import DeterministicAuthProvider


def test_connected_inbox_workflow_is_replay_safe_and_retains_imported_evidence(
    database: Database,
    test_database_url: str,
) -> None:
    admin, specialist = _seed_workspace(database)
    runtime = build_inbox_runtime(
        database=database,
        settings=Settings(
            environment="test",
            auth_mode="deterministic_development",
            model_provider="deterministic",
            embedding_provider="deterministic",
            database_url=test_database_url,
            inbox_connections_enabled=True,
            gmail_adapter_enabled=False,
            inbox_scheduled_sync_enabled=False,
            gmail_push_enabled=False,
            inbox_draft_writeback_enabled=False,
            inbox_ai_data_transfer_enabled=False,
        ),
    )
    assert runtime is not None

    try:
        started = runtime.authorization.start(
            actor=admin,
            include_drafts=False,
            return_path="/connections",
            login_hint=None,
        )
        state = parse_qs(urlsplit(started.authorization_url).query)["state"][0]
        connected = runtime.authorization.complete(
            actor=admin,
            state=state,
            code="deterministic-code",
            correlation_id="phase7-connect",
        )
        with pytest.raises(InboxAuthorizationError):
            runtime.authorization.complete(
                actor=admin,
                state=state,
                code="deterministic-code",
                correlation_id="phase7-connect-replay",
            )

        threads = runtime.browse.list_threads(
            actor=specialist,
            connection_id=connected.connection_public_id,
            page_token=None,
            limit=10,
        )
        assert len(threads.items) == 1

        command = SelectedThreadImportCommand(
            provider_thread_id=threads.items[0].provider_thread_id,
            category=CaseCategory.BILLING_DISPUTE,
            urgency=CaseUrgency.HIGH,
            risk=CaseRisk.HIGH,
            due_at=datetime.now(UTC) + timedelta(days=1),
        )
        first = runtime.imports.import_selected_thread(
            actor=specialist,
            connection_id=connected.connection_public_id,
            command=command,
            correlation_id="phase7-import",
        )
        replay = runtime.imports.import_selected_thread(
            actor=specialist,
            connection_id=connected.connection_public_id,
            command=command,
            correlation_id="phase7-import-replay",
        )
        assert first.case_public_id == replay.case_public_id
        assert first.external_conversation_public_id == replay.external_conversation_public_id
        assert first.imported_messages == 2
        assert replay.imported_messages == 0
        assert replay.duplicate_messages == 2

        first_job, sync_result = runtime.sync.run_manual(
            actor=admin,
            connection_id=connected.connection_public_id,
            trigger_key="phase7-manual-sync",
            worker_id="phase7-worker",
        )
        replayed_job, replay_result = runtime.sync.run_manual(
            actor=admin,
            connection_id=connected.connection_public_id,
            trigger_key="phase7-manual-sync",
            worker_id="phase7-worker-replay",
        )
        assert replayed_job.id == first_job.id
        assert sync_result.claimed_jobs == 1
        assert sync_result.completed_jobs == 1
        assert sync_result.failed_jobs == 0
        assert replay_result.claimed_jobs == 0

        runtime.controls.pause(
            actor=admin,
            connection_id=connected.connection_public_id,
            correlation_id="phase7-pause",
        )
        with pytest.raises(InboxConflict, match="paused"):
            runtime.browse.list_threads(
                actor=specialist,
                connection_id=connected.connection_public_id,
                page_token=None,
                limit=10,
            )
        runtime.controls.resume(
            actor=admin,
            connection_id=connected.connection_public_id,
            correlation_id="phase7-resume",
        )
        assert runtime.browse.list_threads(
            actor=specialist,
            connection_id=connected.connection_public_id,
            page_token=None,
            limit=10,
        ).items

        disconnected = runtime.controls.disconnect(
            actor=admin,
            connection_id=connected.connection_public_id,
            correlation_id="phase7-disconnect",
        )
        assert disconnected.provider_revoked
        with database.session() as session:
            workspace = CaseRepository(session).get_workspace(
                organization_public_id=admin.organization_id,
                case_public_id=first.case_public_id,
            )
        assert workspace is not None
        assert len(workspace.messages) == 2
        assert workspace.draft is None

        reconnect_started = runtime.authorization.start(
            actor=admin,
            include_drafts=False,
            return_path="/connections",
            login_hint=None,
        )
        reconnect_state = parse_qs(urlsplit(reconnect_started.authorization_url).query)[
            "state"
        ][0]
        reconnected = runtime.authorization.complete(
            actor=admin,
            state=reconnect_state,
            code="deterministic-code",
            correlation_id="phase7-reconnect",
        )
        assert reconnected.connection_public_id == connected.connection_public_id
        assert runtime.browse.list_threads(
            actor=specialist,
            connection_id=reconnected.connection_public_id,
            page_token=None,
            limit=10,
        ).items

        with database.session() as session:
            audit_events = session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.subject_id == connected.connection_public_id)
                .order_by(AuditEventModel.occurred_at)
            ).all()
        assert [event.event_type for event in audit_events].count("inbox.connected") == 2
        assert [event.event_type for event in audit_events].count("inbox.disconnected") == 1
        assert {
            "phase7-connect",
            "phase7-pause",
            "phase7-resume",
            "phase7-disconnect",
            "phase7-reconnect",
        }.issubset({event.correlation_id for event in audit_events})
    finally:
        runtime.close()


def _seed_workspace(database: Database) -> tuple[ActorContext, ActorContext]:
    auth = DeterministicAuthProvider()
    admin = auth.authenticate("USR-0003")
    specialist = auth.authenticate("USR-0001")
    assert admin.role is not None
    assert specialist.role is not None
    with database.session() as session:
        organization = OrganizationModel(
            public_id=admin.organization_id,
            name="Phase 7 inbox workspace",
            slug="phase7-inbox-workspace",
        )
        session.add(organization)
        session.flush()
        session.add_all(
            [
                MembershipModel(
                    public_id=admin.actor_id,
                    organization_id=organization.id,
                    subject_id=admin.actor_id,
                    name=admin.name,
                    email=f"{admin.actor_id.lower()}@example.invalid",
                    role=admin.role.value,
                    status="active",
                ),
                MembershipModel(
                    public_id=specialist.actor_id,
                    organization_id=organization.id,
                    subject_id=specialist.actor_id,
                    name=specialist.name,
                    email=f"{specialist.actor_id.lower()}@example.invalid",
                    role=specialist.role.value,
                    status="active",
                ),
            ]
        )
    return admin, specialist
