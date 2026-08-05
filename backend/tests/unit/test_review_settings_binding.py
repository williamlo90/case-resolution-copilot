from decimal import Decimal
from typing import cast

import pytest

from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import DecisionBriefRecord
from app.domain.policies import PolicyEvidenceBundle
from app.domain.reviews import (
    ReviewBundleRecord,
    ReviewFreshness,
    ReviewFreshnessRecord,
    ReviewStatus,
)
from app.domain.settings import ApprovalSettingsValues
from app.security.authentication import DeterministicAuthProvider
from app.services import review_service
from app.services.review_service import (
    ReviewApprovalSettingsProvider,
    ReviewCaseStore,
    ReviewDecisionStore,
    ReviewEvidenceResolver,
    ReviewPolicyStore,
    ReviewService,
    ReviewStore,
)
from tests.builders import (
    valid_case_workspace,
    valid_decision_brief,
    valid_review_bundle,
    valid_review_freshness,
)


class _ReviewStore:
    def __init__(self, bundle: ReviewBundleRecord) -> None:
        self.bundle = bundle

    def get(self, **values: object) -> ReviewBundleRecord:
        del values
        return self.bundle

    def freshness(self, **values: object) -> ReviewFreshnessRecord:
        del values
        return valid_review_freshness()


class _DecisionStore:
    def get_version(self, **values: object) -> DecisionBriefRecord:
        del values
        return valid_decision_brief(
            context_snapshot_ids=[],
            evidence_ids=[],
        )


class _CaseStore:
    def get_workspace(self, **values: object) -> CaseWorkspaceRecord:
        del values
        return valid_case_workspace()


class _PolicyStore:
    def list_evidence_for_case(self, **values: object) -> list[PolicyEvidenceBundle]:
        del values
        return []


class _ApprovalSettings:
    def __init__(self, version: int) -> None:
        self.version = version

    def approval_values(
        self,
        *,
        organization_public_id: str,
    ) -> tuple[ApprovalSettingsValues, int]:
        assert organization_public_id == "ORG-0001"
        return (
            ApprovalSettingsValues(
                administrator_financial_limits={
                    "USD": Decimal("500.00"),
                }
            ),
            self.version,
        )


def _bundle(status: ReviewStatus) -> ReviewBundleRecord:
    return valid_review_bundle(status=status)


def _service(
    bundle: ReviewBundleRecord,
    *,
    settings_version: int,
) -> ReviewService:
    return ReviewService(
        cast(ReviewStore, _ReviewStore(bundle)),
        cast(ReviewCaseStore, _CaseStore()),
        cast(ReviewDecisionStore, _DecisionStore()),
        cast(ReviewPolicyStore, _PolicyStore()),
        cast(ReviewEvidenceResolver, object()),
        approval_settings=cast(
            ReviewApprovalSettingsProvider,
            _ApprovalSettings(settings_version),
        ),
    )


def test_pending_review_becomes_stale_when_approval_settings_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_service,
        "proposal_snapshot_fingerprint",
        lambda brief: "p" * 64,
    )

    detail = _service(
        _bundle(ReviewStatus.PENDING),
        settings_version=2,
    ).get(
        actor=DeterministicAuthProvider().authenticate("USR-0002"),
        review_id="RV-TEST-0001",
    )

    assert detail.freshness.status is ReviewFreshness.STALE
    assert detail.freshness.reason is not None
    assert "Approval rules changed" in detail.freshness.reason
    assert detail.available_decisions == []


def test_completed_review_keeps_historical_rule_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_service,
        "proposal_snapshot_fingerprint",
        lambda brief: "p" * 64,
    )

    detail = _service(
        _bundle(ReviewStatus.APPROVED),
        settings_version=2,
    ).get(
        actor=DeterministicAuthProvider().authenticate("USR-0002"),
        review_id="RV-TEST-0001",
    )

    assert detail.freshness.status is ReviewFreshness.CURRENT
