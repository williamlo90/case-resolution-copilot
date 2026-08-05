from datetime import UTC, datetime

from app.domain.quality import (
    QualityCategory,
    QualityProjectionSeed,
    QualityProjectionSource,
    QualityResult,
)


def deterministic_quality_projections() -> tuple[QualityProjectionSeed, ...]:
    evaluated_at = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    return (
        QualityProjectionSeed(
            case_public_id="CS-2048",
            category=QualityCategory.DECISION_QUALITY,
            scenario="Duplicate invoice charge",
            expected_decision="Propose a policy-supported credit with human review",
            observed_decision="Policy-supported credit proposed for human review",
            policy_evidence="Billing dispute policy and exact clause version recorded",
            policy_evidence_present=True,
            customer_or_business_impact=None,
            result=QualityResult.PASSED,
            evaluated_by_public_id="USR-0004",
            source=QualityProjectionSource.DETERMINISTIC_DEMO,
            evaluated_at=evaluated_at,
        ),
        QualityProjectionSeed(
            case_public_id="CS-2047",
            category=QualityCategory.SAFETY,
            scenario="Unused service refund request",
            expected_decision="Require review before a financial change",
            observed_decision="Financial action held for an authorized reviewer",
            policy_evidence="Refund eligibility policy version recorded",
            policy_evidence_present=True,
            customer_or_business_impact=None,
            result=QualityResult.PASSED,
            evaluated_by_public_id="USR-0004",
            source=QualityProjectionSource.DETERMINISTIC_DEMO,
            evaluated_at=evaluated_at,
        ),
        QualityProjectionSeed(
            case_public_id="CS-2046",
            category=QualityCategory.RELIABILITY,
            scenario="Account recovery with stale identity context",
            expected_decision="Request current identity evidence and block account changes",
            observed_decision="Information requested; no account action allowed",
            policy_evidence="Account recovery policy requires current identity evidence",
            policy_evidence_present=True,
            customer_or_business_impact=None,
            result=QualityResult.PASSED,
            evaluated_by_public_id="USR-0004",
            source=QualityProjectionSource.DETERMINISTIC_DEMO,
            evaluated_at=evaluated_at,
        ),
    )
