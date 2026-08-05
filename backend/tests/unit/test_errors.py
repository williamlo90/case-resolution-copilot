from app.api.errors import error_payload


def test_error_payload_matches_public_contract() -> None:
    assert error_payload(
        code="proposal_version_conflict",
        message="The proposal changed.",
        correlation_id="corr_test",
        details={"expected_version": 1, "current_version": 2},
    ) == {
        "error": {
            "code": "proposal_version_conflict",
            "message": "The proposal changed.",
            "correlation_id": "corr_test",
            "details": {"expected_version": 1, "current_version": 2},
        }
    }
