from collections.abc import Sequence

from app.domain.cases import BusinessObjectType, CaseCategory, CaseWorkspaceRecord
from app.domain.decision_briefs import (
    DecisionProposalState,
    InformationGap,
    ProposedActionDraft,
    ResponseSuggestionStatus,
    SuggestedResponseDraft,
)


def draft_customer_response(
    *,
    workspace: CaseWorkspaceRecord,
    state: DecisionProposalState,
    blocking: Sequence[InformationGap],
    actions: Sequence[ProposedActionDraft],
) -> SuggestedResponseDraft:
    """Build a customer-safe draft from the governed decision controls."""

    if state is DecisionProposalState.INFORMATION_NEEDED:
        return SuggestedResponseDraft(
            subject=_information_needed_subject(workspace.case.category),
            body=_information_needed_body(workspace, blocking),
            status=ResponseSuggestionStatus.BLOCKED,
        )

    action = actions[0] if actions else None
    return SuggestedResponseDraft(
        subject=_review_subject(workspace.case.category),
        body=_review_body(workspace, action),
        status=ResponseSuggestionStatus.READY,
    )


def _information_needed_subject(category: CaseCategory) -> str:
    return {
        CaseCategory.BILLING_DISPUTE: "Information needed for your billing case",
        CaseCategory.REFUND_REQUEST: "Information needed for your refund request",
        CaseCategory.ACCOUNT_ACCESS: "Information needed for account recovery",
        CaseCategory.SERVICE_EXCEPTION: "Information needed for your service case",
    }[category]


def _review_subject(category: CaseCategory) -> str:
    return {
        CaseCategory.BILLING_DISPUTE: "Update on your billing case",
        CaseCategory.REFUND_REQUEST: "Update on your refund request",
        CaseCategory.ACCOUNT_ACCESS: "Update on your account recovery request",
        CaseCategory.SERVICE_EXCEPTION: "Update on your service case",
    }[category]


def _information_needed_body(
    workspace: CaseWorkspaceRecord,
    blocking: Sequence[InformationGap],
) -> str:
    labels = {gap.label for gap in blocking}
    category = workspace.case.category

    if category is CaseCategory.BILLING_DISPUTE and "Second payment reference" in labels:
        detail = _billing_record_observation(workspace)
        request = (
            "Please send the second settled payment reference, or an updated statement "
            "showing both settled charges, once it becomes available. We need that record "
            "to verify a duplicate before considering any billing adjustment."
        )
    elif category is CaseCategory.REFUND_REQUEST and "Service delivery status" in labels:
        detail = "The current records do not confirm whether service delivery has started."
        request = (
            "Please confirm the current delivery status and whether any part of the service "
            "has been used. We need that information before considering a refund."
        )
    elif category is CaseCategory.ACCOUNT_ACCESS and "Identity verification" in labels:
        detail = "The account ownership check is not complete yet."
        request = (
            "Please complete the approved identity-verification step. We need that check "
            "before considering any change to the recovery channel."
        )
    elif category is CaseCategory.SERVICE_EXCEPTION and "Service outcome" in labels:
        detail = "The current records do not confirm a failed or incomplete service."
        request = (
            "Please provide the latest service outcome or supporting record. We need it "
            "before considering a correction."
        )
    else:
        needed = ", ".join(gap.label.lower() for gap in blocking) or "the remaining records"
        detail = f"We still need to confirm {needed} before deciding the outcome."
        request = "We will contact you if an additional record is needed from you."

    internal_check = _internal_check_note(labels)
    paragraphs = [f"Hello {workspace.customer.name},", detail, request]
    if internal_check:
        paragraphs.append(internal_check)
    paragraphs.append("We will update you after these checks are complete.")
    return "\n\n".join(paragraphs)


def _billing_record_observation(workspace: CaseWorkspaceRecord) -> str:
    payment_statuses = [
        context.status.lower()
        for context in workspace.business_contexts
        if context.type is BusinessObjectType.PAYMENT
    ]
    settled_count = payment_statuses.count("settled")
    recorded_count = sum(status in {"captured", "settled"} for status in payment_statuses)
    if settled_count == 1:
        return "Our records currently show one settled payment, not two settled charges."
    if recorded_count == 1:
        return "Our records currently show one captured payment record, not two settled charges."
    if recorded_count > 1:
        return (
            "Our records show multiple payment records, but fewer than two are confirmed "
            "as settled charges."
        )
    return "Our records do not yet confirm two settled charges."


def _internal_check_note(labels: set[str]) -> str | None:
    notes: list[str] = []
    if "Current source context" in labels:
        notes.append("refreshing the current source records")
    if "Applicable policy" in labels:
        notes.append("confirming the rule that applies to this case")
    if "Complete business records" in labels:
        notes.append("consolidating the relevant business records")
    if not notes:
        return None
    return "Our team is also " + " and ".join(notes) + "."


def _review_body(
    workspace: CaseWorkspaceRecord,
    action: ProposedActionDraft | None,
) -> str:
    evidence, proposal, not_completed = _review_language(action)
    return "\n\n".join(
        [
            f"Hello {workspace.customer.name},",
            evidence,
            proposal,
            not_completed,
            "We will update you after the required review is complete.",
        ]
    )


def _review_language(
    action: ProposedActionDraft | None,
) -> tuple[str, str, str]:
    if action is None:
        return (
            "We reviewed the available records for your case.",
            "A proposed resolution has been prepared for review.",
            "No customer-impacting action has been taken yet.",
        )
    return {
        "reverse_duplicate_charge": (
            "We verified two settled payment records for this case.",
            "A reversal of the duplicate charge has been prepared for review.",
            "No reversal has been made yet.",
        ),
        "issue_refund": (
            "The records show that the service order is unused and delivery has not started.",
            "A refund has been prepared for review.",
            "The refund remains pending and has not been issued.",
        ),
        "start_verified_recovery": (
            "The account ownership check is complete.",
            "A controlled account recovery path has been prepared for review.",
            "No recovery-channel change has been made yet.",
        ),
        "apply_service_correction": (
            "The records confirm the failed or incomplete service outcome.",
            "A service correction has been prepared for review.",
            "No correction has been applied yet.",
        ),
    }.get(
        action.type,
        (
            "We reviewed the available records for your case.",
            f"The proposed next step, {action.label.lower()}, has been prepared for review.",
            "No customer-impacting action has been taken yet.",
        ),
    )
