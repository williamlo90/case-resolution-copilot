from app.config import Settings
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
