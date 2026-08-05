from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from app.domain.policies import PolicyApplicability, PolicySourceKind


class DeterministicPolicySeed(BaseModel):
    model_config = ConfigDict(frozen=True)

    public_id: str
    title: str
    description: str
    source_kind: PolicySourceKind
    source_name: str
    source_text: str
    applicability: PolicyApplicability
    effective_from: datetime


class DeterministicPolicySourceSimulator:
    def fetch_policies(self) -> tuple[DeterministicPolicySeed, ...]:
        return deterministic_policies()


def deterministic_policies() -> tuple[DeterministicPolicySeed, ...]:
    effective_from = datetime(2026, 1, 1, tzinfo=UTC)
    return (
        DeterministicPolicySeed(
            public_id="POL-1008",
            title="Billing adjustments",
            description="Rules for duplicate charges, credits, and refund eligibility.",
            source_kind=PolicySourceKind.MANUAL,
            source_name="Deterministic billing policy",
            source_text=(
                "## Duplicate charges\n"
                "A verified duplicate invoice charge may be reversed or credited after the "
                "invoice and payment references are confirmed.\n\n"
                "## Refund eligibility\n"
                "An unused service order may be refunded when delivery has not started and no "
                "non-refundable commitment is recorded."
            ),
            applicability=PolicyApplicability(
                decision_scope="billing_adjustment",
                case_categories=["billing_dispute", "refund_request"],
                products=["all"],
                regions=["all"],
                channels=["all"],
                customer_tiers=["all"],
            ),
            effective_from=effective_from,
        ),
        DeterministicPolicySeed(
            public_id="POL-1007",
            title="Account recovery",
            description="Identity checks and safe account restoration requirements.",
            source_kind=PolicySourceKind.MANUAL,
            source_name="Deterministic account recovery policy",
            source_text=(
                "## Identity verification\n"
                "Account recovery requires a verified ownership check before a recovery channel "
                "or multi-factor authentication setting is changed.\n\n"
                "## Unsafe recovery\n"
                "Recovery must stop and move to specialist review when ownership evidence is "
                "missing or conflicts with the account record."
            ),
            applicability=PolicyApplicability(
                decision_scope="account_recovery",
                case_categories=["account_access"],
                products=["all"],
                regions=["all"],
                channels=["all"],
                customer_tiers=["all"],
            ),
            effective_from=effective_from,
        ),
        DeterministicPolicySeed(
            public_id="POL-1006",
            title="Service exceptions",
            description="Resolution boundaries for failed or incomplete service delivery.",
            source_kind=PolicySourceKind.MANUAL,
            source_name="Deterministic service exception policy",
            source_text=(
                "## Service failure\n"
                "A service exception may be resolved only after the order or delivery record "
                "confirms the failed outcome and the customer impact.\n\n"
                "## Escalation\n"
                "A consequential correction requires review when the provider outcome is unknown "
                "or the proposed change exceeds specialist authority."
            ),
            applicability=PolicyApplicability(
                decision_scope="service_exception",
                case_categories=["service_exception"],
                products=["all"],
                regions=["all"],
                channels=["all"],
                customer_tiers=["all"],
            ),
            effective_from=effective_from,
        ),
        DeterministicPolicySeed(
            public_id="POL-1005",
            title="Customer data handling",
            description="Privacy limits for evidence and customer communications.",
            source_kind=PolicySourceKind.MANUAL,
            source_name="Deterministic privacy policy",
            source_text=(
                "## Minimum necessary data\n"
                "Case evidence and audit records must contain only the customer data required to "
                "explain and authorize the support decision.\n\n"
                "## Restricted content\n"
                "Secrets, raw provider payloads, and private reasoning must not be copied into "
                "customer messages or business audit records."
            ),
            applicability=PolicyApplicability(
                decision_scope="privacy_handling",
                case_categories=["all"],
                products=["all"],
                regions=["all"],
                channels=["all"],
                customer_tiers=["all"],
            ),
            effective_from=effective_from,
        ),
    )
