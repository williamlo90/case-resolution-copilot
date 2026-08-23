from datetime import UTC, datetime

from app.api.routes.inbox_connections import _thread_response
from app.config import Settings
from app.domain.inbox import ProviderThreadSummary
from app.main import create_app


def test_connected_inbox_routes_are_registered_without_a_send_route() -> None:
    schema = create_app(Settings()).openapi()
    paths = set(schema["paths"])

    assert "/api/connections/inbox/authorize" in paths
    assert "/api/connections/inbox/callback" in paths
    assert "/api/connections/{connection_id}/inbox/status" in paths
    assert "/api/connections/{connection_id}/imports" in paths
    assert "/api/connections/{connection_id}/sync" in paths
    assert "/api/cases/{case_id}/response-draft/deliver" in paths
    assert "/api/cases/{case_id}/response-draft/delivery" in paths
    assert "/api/draft-deliveries/{delivery_id}/reconcile" in paths
    assert "/api/internal/inbox-sync/drain" in paths
    assert "/api/internal/policy-index/drain" in paths
    assert all("/send" not in path for path in paths)


def test_thread_summary_is_mapped_to_the_public_api_schema() -> None:
    latest_message_at = datetime(2026, 8, 23, 13, 14, tzinfo=UTC)

    response = _thread_response(
        ProviderThreadSummary(
            provider_thread_id="thread-42",
            subject="Synthetic billing question",
            latest_message_at=latest_message_at,
        )
    )

    assert response.model_dump() == {
        "provider_thread_id": "thread-42",
        "subject": "Synthetic billing question",
        "latest_message_at": latest_message_at,
    }
