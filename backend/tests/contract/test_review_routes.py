from fastapi.testclient import TestClient

from app.api.routes.reviews import _translate
from app.config import Settings
from app.domain.reviews import (
    InvalidReviewCursor,
    ReviewAuthorityDenied,
    ReviewDecisionNotAllowed,
)
from app.main import create_app


def test_review_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.get("/api/reviews")
        read_unavailable = client.get(
            "/api/reviews",
            headers={"X-Actor-ID": "USR-0004"},
        )
        spoofed_reserve = client.post(
            "/api/reviews/RV-TEST/reserve",
            headers={
                "X-Actor-ID": "USR-0001",
                "X-Actor-Role": "administrator",
            },
            json={"expected_version": 1},
        )
        reserve_unavailable = client.post(
            "/api/reviews/RV-TEST/reserve",
            headers={"X-Actor-ID": "USR-0002"},
            json={"expected_version": 1},
        )
        submit_unavailable = client.post(
            "/api/cases/CS-TEST/proposals/1/reviews",
            headers={"X-Actor-ID": "USR-0001"},
            json={"expected_case_version": 1},
        )

    assert unauthenticated.status_code == 401
    assert read_unavailable.status_code == 503
    assert spoofed_reserve.status_code == 403
    assert spoofed_reserve.json()["error"]["code"] == "review_reserve_forbidden"
    assert reserve_unavailable.status_code == 503
    assert submit_unavailable.status_code == 503


def test_review_errors_keep_authority_input_and_state_failures_distinct() -> None:
    authority = _translate(ReviewAuthorityDenied("Administrator authority is required."))
    cursor = _translate(InvalidReviewCursor("The review cursor is invalid."))
    decision = _translate(ReviewDecisionNotAllowed("Approval is not available for this review."))

    assert (authority.status_code, authority.code) == (
        403,
        "review_authority_denied",
    )
    assert (cursor.status_code, cursor.code) == (400, "invalid_review_cursor")
    assert (decision.status_code, decision.code) == (
        409,
        "review_decision_not_allowed",
    )
