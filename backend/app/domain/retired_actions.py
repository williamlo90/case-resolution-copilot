"""Read-only compatibility for stored actions outside the current product scope."""

RETIRED_ACTION_TYPES = frozenset(
    {
        "correct_billing_address",
        "change_draft_currency",
        "regenerate_invoice_locale",
        "credit_removed_seats",
        "attach_purchase_order",
        "refund_course_fee",
        "refund_unstarted_premium",
        "rename_account",
        "revoke_compromised_sessions",
        "change_recovery_email",
    }
)
