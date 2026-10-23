"""Small, complete synthetic inputs for the interactive V2 walkthrough."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.cases import CaseCreate
from app.domain.identity import ActorContext
from app.domain.policies import PolicyApplicability, PolicyWorkspaceRecord
from app.services.policy_service import PolicyService

SCENARIOS = {"verified_reopen", "sop_revision", "timeout_recovery"}


def applicability() -> PolicyApplicability:
    return PolicyApplicability(
        decision_scope="course_refund",
        case_categories=["refund_request"],
        products=["all"],
        regions=["all"],
        channels=["all"],
        customer_tiers=["all"],
    )


def policy_text(*, revised: bool = False) -> str:
    maximum = 10000 if revised else 50000
    return (
        "## Course fee refund\n"
        "Refund an unused course to its original purchaser only when attendance is 0 percent, "
        "the request is within 30 days, and owner, amount, currency and target are verified. "
        f"Human approval is mandatory. Maximum authorized refund is USD {maximum / 100:.2f}.\n\n"
        "## Completion\nRead back the target ledger before closure. A receipt alone is not "
        "completion. Unknown outcomes must be reconciled; do not issue another refund.\n\n"
        "```case-resolution-rules\n"
        + json.dumps(
            {
                "schema_version": 1,
                "rules": [
                    {"kind": "refund_window", "max_days": 30},
                    {
                        "kind": "controlled_operation",
                        "action_type": "refund_course_fee",
                        "max_amount_minor": maximum,
                        "currency": "USD",
                    },
                ],
            }
        )
        + "\n```"
    )


def case_fixture(token: str) -> CaseCreate:
    now = datetime.now(UTC)
    target = f"COURSE-{token}"
    owner = f"CUSTOMER-{token}"
    return CaseCreate.model_validate(
        {
            "public_id": f"CS-DEMO-{token}",
            "source_id": f"v2-demo:{token}",
            "external_reference": f"DEMO-{token}",
            "category": "refund_request",
            "issue": "Refund USD 240 for an unused course; verify the outcome before closing.",
            "status": "investigating",
            "urgency": "medium",
            "risk": "medium",
            "due_at": now + timedelta(days=2),
            "impact_amount": Decimal("240.00"),
            "impact_currency": "USD",
            "source_checked_at": now,
            "request": {
                "channel": "email",
                "customer_message": (
                    "I purchased the course five days ago and have not attended. Please refund "
                    "USD 240 to the original purchaser and confirm the result."
                ),
                "summary": "Unused course refund, USD 240, original purchaser.",
                "received_at": now,
            },
            "customer": {
                "customer_id": owner,
                "name": "Demo Customer",
                "tier": "standard",
                "locale": "en-US",
                "contact": "customer@example.test",
            },
            "business_contexts": [
                {
                    "public_id": f"BO-DEMO-{token}",
                    "type": "order",
                    "label": "Verified course record",
                    "source": "synthetic_course_register",
                    "source_reference": target,
                    "status": "unused",
                    "captured_at": now,
                    "checked_at": now,
                    "fields": {
                        "requested_operation": "refund_course_fee",
                        "requested_target": target,
                        "original_recipient": owner,
                        "authorized_recipient": owner,
                        "authorized_reason_code": "unused_course",
                        "authorized_amount_minor": "24000",
                        "authorized_currency": "USD",
                        "attendance_percent": "0",
                        "purchased_at": (now - timedelta(days=5)).isoformat(),
                        "delivery_state": "not_started",
                        "supporting_record": "verified",
                    },
                }
            ],
        }
    )


def publish_draft(
    service: PolicyService,
    workspace: PolicyWorkspaceRecord,
    actor: ActorContext,
    correlation_id: str,
) -> PolicyWorkspaceRecord:
    draft = max(workspace.versions, key=lambda v: v.version.version).version
    reviewed = service.submit_review(
        actor=actor,
        policy_id=workspace.policy.public_id,
        version_number=draft.version,
        expected_policy_version=workspace.policy.version,
        expected_version=draft.record_version,
        correlation_id=correlation_id,
    )
    version = max(reviewed.versions, key=lambda v: v.version.version).version
    return service.publish(
        actor=actor,
        policy_id=workspace.policy.public_id,
        version_number=version.version,
        expected_policy_version=reviewed.policy.version,
        expected_version=version.record_version,
        effective_from=datetime.now(UTC),
        correlation_id=correlation_id,
    )
