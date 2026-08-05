from app.tools.redaction import redact


def test_redaction_removes_sensitive_fields_recursively() -> None:
    payload = {
        "customer": {
            "name": "Maya Chen",
            "email": "maya@example.test",
        },
        "case_id": "CASE-2048",
        "message": "Customer-specific free text",
        "metadata": {
            "token": "provider-secret",
            "reason_code": "duplicate_charge",
        },
    }

    assert redact(payload) == {
        "customer": {
            "name": "[REDACTED]",
            "email": "[REDACTED]",
        },
        "case_id": "CASE-2048",
        "message": "[REDACTED]",
        "metadata": {
            "token": "[REDACTED]",
            "reason_code": "duplicate_charge",
        },
    }
