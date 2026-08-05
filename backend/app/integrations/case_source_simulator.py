from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.cases import (
    BusinessObjectCreate,
    BusinessObjectType,
    CaseCategory,
    CaseCreate,
    CaseRequestCreate,
    CaseRisk,
    CaseStatus,
    CaseUrgency,
    CustomerContextCreate,
    CustomerTier,
    RequestChannel,
    SourceFreshness,
)


class CaseSourceAdapter(Protocol):
    def fetch_cases(self) -> tuple[CaseCreate, ...]: ...


class DeterministicCaseSourceSimulator:
    """Credential-free case source used for development and fixed evaluations."""

    def fetch_cases(self) -> tuple[CaseCreate, ...]:
        return deterministic_cases()


def deterministic_cases() -> tuple[CaseCreate, ...]:
    checked_at = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
    return (
        CaseCreate(
            public_id="CS-2048",
            source_id="support-inbox:case-2048",
            external_reference="BILL-78412",
            category=CaseCategory.BILLING_DISPUTE,
            issue="Customer disputes a duplicate invoice charge",
            status=CaseStatus.NEW,
            urgency=CaseUrgency.CRITICAL,
            risk=CaseRisk.HIGH,
            due_at=datetime(2026, 7, 22, 10, 30, tzinfo=UTC),
            impact_amount=Decimal("480000.00"),
            impact_currency="IDR",
            source_freshness=SourceFreshness.CURRENT,
            source_checked_at=checked_at,
            request=CaseRequestCreate(
                channel=RequestChannel.EMAIL,
                customer_message=(
                    "I was charged twice for the same invoice. Please check before the next "
                    "billing cycle."
                ),
                summary="Possible duplicate charge on a paid invoice.",
                received_at=datetime(2026, 7, 21, 7, 42, tzinfo=UTC),
            ),
            customer=CustomerContextCreate(
                customer_id="CUS-1082",
                name="Nadia Prasetyo",
                tier=CustomerTier.VIP,
                locale="id-ID",
                contact="nadia.prasetyo@example.com",
            ),
            business_contexts=[
                BusinessObjectCreate(
                    public_id="CTX-2048-INVOICE",
                    type=BusinessObjectType.INVOICE,
                    label="Invoice INV-78412",
                    source="billing-simulator",
                    source_reference="INV-78412",
                    status="paid",
                    fields={
                        "amount": "480000.00",
                        "currency": "IDR",
                        "billing_period": "2026-07",
                    },
                    captured_at=checked_at,
                    freshness=SourceFreshness.CURRENT,
                    checked_at=checked_at,
                ),
                BusinessObjectCreate(
                    public_id="CTX-2048-PAYMENT",
                    type=BusinessObjectType.PAYMENT,
                    label="Payment PAY-99182",
                    source="payments-simulator",
                    source_reference="PAY-99182",
                    status="captured",
                    fields={
                        "amount": "480000.00",
                        "currency": "IDR",
                        "attempt_count": "2",
                    },
                    captured_at=checked_at,
                    freshness=SourceFreshness.CURRENT,
                    checked_at=checked_at,
                ),
            ],
        ),
        CaseCreate(
            public_id="CS-2047",
            source_id="support-chat:case-2047",
            external_reference="ORDER-52891",
            category=CaseCategory.REFUND_REQUEST,
            issue="Customer requests a refund for an unused service order",
            status=CaseStatus.INVESTIGATING,
            urgency=CaseUrgency.HIGH,
            risk=CaseRisk.MEDIUM,
            due_at=datetime(2026, 7, 22, 14, 0, tzinfo=UTC),
            impact_amount=Decimal("125.00"),
            impact_currency="USD",
            source_freshness=SourceFreshness.CURRENT,
            source_checked_at=checked_at,
            request=CaseRequestCreate(
                channel=RequestChannel.CHAT,
                customer_message=(
                    "The service was never used. Can you confirm whether this order can be "
                    "refunded?"
                ),
                summary="Refund request for an unused service order.",
                received_at=datetime(2026, 7, 21, 6, 15, tzinfo=UTC),
            ),
            customer=CustomerContextCreate(
                customer_id="CUS-1044",
                name="Marcus Lee",
                tier=CustomerTier.ENTERPRISE,
                locale="en-SG",
                contact="marcus.lee@example.com",
            ),
            business_contexts=[
                BusinessObjectCreate(
                    public_id="CTX-2047-ORDER",
                    type=BusinessObjectType.ORDER,
                    label="Service order ORDER-52891",
                    source="orders-simulator",
                    source_reference="ORDER-52891",
                    status="unused",
                    fields={
                        "amount": "125.00",
                        "currency": "USD",
                        "delivery_state": "not_started",
                    },
                    captured_at=checked_at,
                    freshness=SourceFreshness.CURRENT,
                    checked_at=checked_at,
                )
            ],
        ),
        CaseCreate(
            public_id="CS-2046",
            source_id="support-webhook:case-2046",
            external_reference="ACCOUNT-39018",
            category=CaseCategory.ACCOUNT_ACCESS,
            issue="Account owner cannot complete recovery after changing phone number",
            status=CaseStatus.INFORMATION_NEEDED,
            urgency=CaseUrgency.MEDIUM,
            risk=CaseRisk.HIGH,
            due_at=datetime(2026, 7, 23, 3, 0, tzinfo=UTC),
            impact_amount=None,
            impact_currency=None,
            source_freshness=SourceFreshness.STALE,
            source_checked_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
            request=CaseRequestCreate(
                channel=RequestChannel.WEBHOOK,
                customer_message=(
                    "My recovery code goes to an old phone number and I cannot access the account."
                ),
                summary="Recovery is blocked by an outdated phone number.",
                received_at=datetime(2026, 7, 21, 4, 55, tzinfo=UTC),
            ),
            customer=CustomerContextCreate(
                customer_id="CUS-0997",
                name="Elena Garcia",
                tier=CustomerTier.STANDARD,
                locale="en-US",
                contact="elena.garcia@example.com",
            ),
            business_contexts=[
                BusinessObjectCreate(
                    public_id="CTX-2046-ACCOUNT",
                    type=BusinessObjectType.ACCOUNT,
                    label="Account ACCOUNT-39018",
                    source="identity-simulator",
                    source_reference="ACCOUNT-39018",
                    status="recovery_blocked",
                    fields={
                        "mfa_state": "enabled",
                        "recovery_channel": "phone",
                        "identity_check": "pending",
                    },
                    captured_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
                    freshness=SourceFreshness.STALE,
                    checked_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
                )
            ],
        ),
    )
