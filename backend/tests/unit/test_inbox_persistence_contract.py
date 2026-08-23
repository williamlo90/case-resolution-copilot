from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import ForeignKeyConstraint, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.orm import Session

from app.domain.inbox import DraftDeliveryStatus, DraftReceipt, InboxConflict
from app.persistence.connection_persistence.inbox import InboxConnectionWriter
from app.persistence.inbox import drafts as inbox_drafts
from app.persistence.inbox.drafts import InboxDraftRepository
from app.persistence.inbox.sync_jobs import _claim_statement
from app.persistence.models import (
    ConnectionCredentialEnvelopeModel,
    ConnectionModel,
    ExternalAttachmentModel,
    ExternalConversationModel,
    ExternalMessageModel,
    GovernedPolicyClauseEmbeddingV2Model,
    InboxConnectionProfileModel,
    InboxDraftDeliveryModel,
    InboxOAuthSessionModel,
    InboxSyncCheckpointModel,
    InboxSyncJobModel,
    PolicyIndexJobModel,
)
from app.persistence.policy_indexing.job_queue import _enqueue_statement

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)


def _draft_delivery(
    *,
    status: DraftDeliveryStatus,
    lease_owner: str | None,
    lease_expires_at: datetime | None,
) -> InboxDraftDeliveryModel:
    return InboxDraftDeliveryModel(
        id=uuid4(),
        public_id="IDL-UNIT-0001",
        organization_id=uuid4(),
        case_id=uuid4(),
        external_conversation_id=uuid4(),
        connection_id=uuid4(),
        response_draft_id=uuid4(),
        response_draft_version=1,
        review_id=uuid4(),
        decision_fingerprint="a" * 64,
        evidence_fingerprint="b" * 64,
        policy_fingerprint="c" * 64,
        conversation_fingerprint="d" * 64,
        response_fingerprint="e" * 64,
        provider_thread_id="thread-1",
        recipient="customer@example.com",
        subject_snapshot="Invoice question",
        body_hash="f" * 64,
        in_reply_to=None,
        references=[],
        idempotency_key="1" * 64,
        status=status.value,
        provider_draft_id=None,
        provider_message_id=None,
        attempt_count=1,
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        last_error_code=None,
        completed_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _table(model: type[object]) -> Table:
    table = getattr(model, "__table__", None)
    assert isinstance(table, Table)
    return table


def _constraint_names(
    model: type[object],
    constraint_type: type[ForeignKeyConstraint] | type[UniqueConstraint],
) -> set[str]:
    return {
        constraint.name
        for constraint in _table(model).constraints
        if isinstance(constraint, constraint_type)
        and isinstance(constraint.name, str)
    }


def test_connected_inbox_children_use_tenant_scoped_foreign_keys() -> None:
    expected = {
        InboxConnectionProfileModel: {"fk_inbox_profiles_org_connection"},
        ConnectionCredentialEnvelopeModel: {
            "fk_connection_credentials_org_connection"
        },
        InboxOAuthSessionModel: {"fk_inbox_oauth_org_actor"},
        ExternalConversationModel: {
            "fk_external_conversations_org_connection",
            "fk_external_conversations_org_case",
            "fk_external_conversations_org_thread",
        },
        ExternalMessageModel: {
            "fk_external_messages_org_connection",
            "fk_external_messages_org_conversation",
            "fk_external_messages_org_local_message",
        },
        ExternalAttachmentModel: {"fk_external_attachments_org_message"},
        InboxSyncCheckpointModel: {"fk_inbox_checkpoints_org_connection"},
        InboxSyncJobModel: {"fk_inbox_sync_jobs_org_connection"},
        InboxDraftDeliveryModel: {
            "fk_inbox_draft_deliveries_org_case",
            "fk_inbox_draft_deliveries_org_connection",
            "fk_inbox_draft_deliveries_org_conversation",
            "fk_inbox_draft_deliveries_org_response_draft",
            "fk_inbox_draft_deliveries_org_review",
        },
    }
    for model, names in expected.items():
        assert names <= _constraint_names(model, ForeignKeyConstraint)


def test_inbox_credentials_and_oauth_sessions_never_define_plaintext_columns() -> None:
    columns = {
        column.name
        for model in (ConnectionCredentialEnvelopeModel, InboxOAuthSessionModel)
        for column in _table(model).columns
    }

    assert {
        "access_token",
        "refresh_token",
        "state",
        "code_verifier",
        "verifier_plaintext",
    }.isdisjoint(columns)
    assert {"ciphertext", "nonce", "authentication_tag"} <= columns
    assert "state_hash" in columns


def test_policy_v2_rows_keep_tenant_identity_in_persistence_constraints() -> None:
    assert "fk_policy_clause_embeddings_v2_clause" in _constraint_names(
        GovernedPolicyClauseEmbeddingV2Model,
        ForeignKeyConstraint,
    )
    assert "fk_policy_index_jobs_version" in _constraint_names(
        PolicyIndexJobModel,
        ForeignKeyConstraint,
    )
    assert "uq_policy_clause_embeddings_v2_org_clause_profile" in _constraint_names(
        GovernedPolicyClauseEmbeddingV2Model,
        UniqueConstraint,
    )


def test_inbox_reauthorization_cannot_replace_the_historical_mailbox() -> None:
    organization_id = uuid4()
    connection_id = uuid4()
    connection = ConnectionModel(
        id=connection_id,
        public_id="CON-INBOX-EXISTING",
        organization_id=organization_id,
        name="Inbox - original@example.com",
        provider_type="inbox",
        adapter_key="gmail",
        environment="sandbox",
        health="healthy",
        last_checked_at=NOW,
        credential_status="connected",
        read_capabilities=["read_conversations"],
        write_capabilities=[],
        action_types=[],
        affected_work=["case_import"],
        runtime_config_fingerprint=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    profile = InboxConnectionProfileModel(
        id=uuid4(),
        public_id="INP-CON-INBOX-EXISTING",
        organization_id=organization_id,
        connection_id=connection_id,
        provider_account_id="google-account-original",
        account_address="original@example.com",
        import_mode="manual",
        label_filter=["INBOX"],
        initial_window_days=7,
        initial_item_limit=25,
        watch_expires_at=None,
        last_successful_sync_at=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    session = MagicMock(spec=Session)
    session.scalar.side_effect = [connection, profile]

    with pytest.raises(InboxConflict, match="different inbox account"):
        InboxConnectionWriter(session).connect(
            organization_id=organization_id,
            account_address="replacement@example.com",
            provider_account_id="google-account-replacement",
            adapter_key="gmail",
            read_capabilities=["read_conversations"],
            write_capabilities=[],
        )

    assert connection.name == "Inbox - original@example.com"
    session.flush.assert_not_called()


def test_sync_claim_serializes_each_connection_and_skips_active_leases() -> None:
    compiled = str(
        _claim_statement(now=NOW, limit=5).compile(
            dialect=PGDialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "row_number() over (partition by inbox_sync_jobs.organization_id" in compiled
    assert "inbox_sync_jobs.connection_id" in compiled
    assert "not (exists" in compiled
    assert "inbox_sync_jobs_1.status = 'running'" in compiled
    assert "for update of inbox_sync_jobs, connections skip locked" in compiled


def test_policy_index_enqueue_ignores_a_concurrent_duplicate_job() -> None:
    compiled = str(
        _enqueue_statement(
            organization_id=uuid4(),
            policy_id=uuid4(),
            policy_version_id=uuid4(),
            profile_id=uuid4(),
            source_content_fingerprint="a" * 64,
            job_key="b" * 64,
            page_budget=16,
        ).compile(dialect=PGDialect())  # type: ignore[no-untyped-call]
    ).lower()

    assert "on conflict on constraint uq_policy_index_jobs_key do nothing" in compiled


def test_draft_reconciliation_cannot_clear_an_active_worker_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inbox_drafts, "utc_now", lambda: NOW)
    delivery = _draft_delivery(
        status=DraftDeliveryStatus.RUNNING,
        lease_owner="worker-active",
        lease_expires_at=NOW + timedelta(days=1),
    )
    session = MagicMock(spec=Session)
    session.scalar.return_value = delivery

    with pytest.raises(InboxConflict, match="not ready for reconciliation"):
        InboxDraftRepository(session).record_failure(
            organization_id=delivery.organization_id,
            delivery_id=delivery.id,
            status=DraftDeliveryStatus.RECOVERY_REQUIRED,
            error_code="reconciliation_unavailable",
            expected_worker_id=None,
        )

    assert delivery.status == DraftDeliveryStatus.RUNNING.value
    session.flush.assert_not_called()


def test_draft_worker_completion_uses_compare_and_set_ownership() -> None:
    delivery = _draft_delivery(
        status=DraftDeliveryStatus.RUNNING,
        lease_owner="worker-active",
        lease_expires_at=NOW + timedelta(days=1),
    )
    session = MagicMock(spec=Session)
    session.scalar.return_value = delivery

    with pytest.raises(InboxConflict, match="owned by another worker"):
        InboxDraftRepository(session).complete(
            organization_id=delivery.organization_id,
            delivery_id=delivery.id,
            receipt=DraftReceipt(
                provider_draft_id="draft-1",
                provider_message_id="message-1",
                provider_thread_id="thread-1",
                created_at=NOW,
            ),
            expected_worker_id="worker-stale",
        )

    assert delivery.provider_draft_id is None
    session.flush.assert_not_called()
