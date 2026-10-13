import logging

import pytest
from pydantic import ValidationError

from app.services.lifecycle_telemetry import LifecycleSpan, provider_span, stage_span


@pytest.mark.parametrize(
    "field", ["correlation_id", "subject_id", "stage", "duration_ms", "outcome"]
)
def test_missing_stage_fields_are_rejected(field):
    data = dict(
        correlation_id="request-1",
        subject_id="case-1",
        stage="db",
        duration_ms=1,
        outcome="completed",
    )
    del data[field]
    with pytest.raises(ValidationError):
        LifecycleSpan.model_validate(data)


def test_nested_provider_timing_inherits_identity_and_records_failure(caplog):
    with (
        caplog.at_level(logging.INFO),
        pytest.raises(TimeoutError),
        stage_span("request-1", "case-1", "decision"),
        provider_span(),
    ):
        raise TimeoutError("secret provider payload")
    records = [r for r in caplog.records if r.msg == "case.lifecycle_stage"]
    assert [r.stage for r in records] == ["provider", "decision"]
    assert all(r.correlation_id == "request-1" and r.subject_id == "case-1" for r in records)
    assert all(r.outcome == "failed" and r.duration_ms >= 0 for r in records)
    assert "secret" not in caplog.text
    with provider_span():
        pass
    assert len(caplog.records) == 2
