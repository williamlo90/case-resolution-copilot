from datetime import UTC, datetime
from hashlib import sha256

from app.domain.inbox import (
    AccessCredential,
    CreateDraftRequest,
    FindDraftRequest,
)
from app.integrations.deterministic_inbox import DeterministicInboxGateway


def _access() -> AccessCredential:
    return AccessCredential(
        access_token="deterministic-access-token",
        expires_at=datetime(2026, 8, 12, 2, 0, tzinfo=UTC),
    )


def test_deterministic_inbox_reads_a_bounded_thread() -> None:
    gateway = DeterministicInboxGateway(
        clock=lambda: datetime(2026, 8, 12, 1, 30, tzinfo=UTC)
    )

    page = gateway.list_threads(
        access=_access(),
        label_filter=("INBOX",),
        after=datetime(2026, 8, 1, tzinfo=UTC),
        page_token=None,
        limit=10,
    )
    thread = gateway.get_thread(
        access=_access(),
        provider_thread_id=page.items[0].provider_thread_id,
    )

    assert len(page.items) == 1
    assert [message.direction.value for message in thread.messages] == [
        "inbound",
        "outbound",
    ]
    assert all(len(message.sanitized_content_hash) == 64 for message in thread.messages)


def test_deterministic_draft_creation_is_idempotent_and_reconcilable() -> None:
    gateway = DeterministicInboxGateway(
        clock=lambda: datetime(2026, 8, 12, 1, 30, tzinfo=UTC)
    )
    correlation_key = sha256(b"authorized-draft").hexdigest()
    request = CreateDraftRequest(
        provider_thread_id="thread-billing-001",
        recipient="nadia@example.com",
        subject="Re: Duplicate charge on INV-78412",
        body="We confirmed the next safe step.",
        correlation_key=correlation_key,
    )

    first = gateway.create_reply_draft(access=_access(), request=request)
    second = gateway.create_reply_draft(access=_access(), request=request)
    found = gateway.find_draft(
        access=_access(),
        request=FindDraftRequest(
            provider_thread_id=request.provider_thread_id,
            correlation_key=correlation_key,
            recipient=request.recipient,
            subject=request.subject,
            body_hash=sha256(request.body.encode()).hexdigest(),
            not_before=datetime(2026, 8, 12, 1, 0, tzinfo=UTC),
        ),
    )

    assert first == second
    assert found.status == "found"
    assert found.receipt == first
