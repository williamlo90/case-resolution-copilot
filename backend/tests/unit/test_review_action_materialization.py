from typing import cast

import pytest

from app.domain.reviews import (
    ReviewBundleRecord,
    ReviewDecision,
    ReviewDetailRecord,
)
from app.security.authentication import DeterministicAuthProvider
from app.services import review_service
from app.services.review_service import (
    ApprovedActionMaterializer,
    ReviewCaseStore,
    ReviewDecisionStore,
    ReviewEvidenceResolver,
    ReviewPolicyStore,
    ReviewService,
    ReviewStore,
)
from tests.builders import (
    valid_decision_brief,
    valid_review_bundle,
    valid_review_freshness,
)


class _Store:
    def __init__(self, bundle: ReviewBundleRecord) -> None:
        self.bundle = bundle
        self.decisions: list[ReviewDecision] = []

    def get(self, **values: object) -> ReviewBundleRecord:
        del values
        return self.bundle

    def decide(self, **values: object) -> ReviewBundleRecord:
        self.decisions.append(cast(ReviewDecision, values["decision"]))
        return self.bundle


class _Materializer:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def materialize(self, **values: str) -> None:
        self.calls.append(values)


def _service(
    *,
    store: _Store,
    materializer: _Materializer,
    monkeypatch: pytest.MonkeyPatch,
    decision: ReviewDecision,
) -> tuple[ReviewService, ReviewDetailRecord]:
    bundle = store.bundle
    detail = ReviewDetailRecord(
        bundle=bundle,
        brief=valid_decision_brief(),
        business_contexts=[],
        evidence=[],
        freshness=valid_review_freshness(),
        available_decisions=[decision],
    )
    service = ReviewService(
        cast(ReviewStore, store),
        cast(ReviewCaseStore, object()),
        cast(ReviewDecisionStore, object()),
        cast(ReviewPolicyStore, object()),
        cast(ReviewEvidenceResolver, object()),
        cast(ApprovedActionMaterializer, materializer),
    )
    monkeypatch.setattr(service, "_detail", lambda **values: detail)
    monkeypatch.setattr(
        review_service,
        "allowed_decisions",
        lambda **values: [decision],
    )
    return service, detail


def test_approval_materializes_action_in_the_review_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store(valid_review_bundle())
    materializer = _Materializer()
    service, detail = _service(
        store=store,
        materializer=materializer,
        monkeypatch=monkeypatch,
        decision=ReviewDecision.APPROVE,
    )

    result = service.decide(
        actor=DeterministicAuthProvider().authenticate("USR-0003"),
        review_id=store.bundle.review.public_id,
        expected_version=1,
        snapshot_fingerprint=store.bundle.snapshot.snapshot_fingerprint,
        decision=ReviewDecision.APPROVE,
        reason="The exact reviewed action is authorized.",
        correlation_id="corr-test",
    )

    assert result is detail
    assert store.decisions == [ReviewDecision.APPROVE]
    assert materializer.calls == [
        {
            "organization_public_id": "ORG-0001",
            "review_public_id": "RV-TEST-0001",
            "correlation_id": "corr-test",
        }
    ]


def test_non_approval_decision_never_materializes_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store(valid_review_bundle())
    materializer = _Materializer()
    service, _ = _service(
        store=store,
        materializer=materializer,
        monkeypatch=monkeypatch,
        decision=ReviewDecision.REJECT,
    )

    service.decide(
        actor=DeterministicAuthProvider().authenticate("USR-0003"),
        review_id=store.bundle.review.public_id,
        expected_version=1,
        snapshot_fingerprint=store.bundle.snapshot.snapshot_fingerprint,
        decision=ReviewDecision.REJECT,
        reason="The proposed action is not authorized.",
        correlation_id="corr-test",
    )

    assert store.decisions == [ReviewDecision.REJECT]
    assert materializer.calls == []
