from app.integrations.case_webhook import SignedCaseWebhookEvent


def _payload() -> dict[str, object]:
    return {
        "event_id": "helpdesk:case-1001",
        "external_reference": "INV-1001",
        "category": "billing_dispute",
        "issue": "Customer reports a duplicate invoice charge",
        "urgency": "high",
        "risk": "medium",
        "due_at": "2026-07-29T12:00:00Z",
        "impact_amount": "125.00",
        "impact_currency": "USD",
        "source_freshness": "current",
        "source_checked_at": "2026-07-28T12:00:00Z",
        "request": {
            "channel": "webhook",
            "customer_message": "I was charged twice.",
            "summary": "Possible duplicate charge.",
            "received_at": "2026-07-28T11:55:00Z",
        },
        "customer": {
            "customer_id": "CUS-1001",
            "name": "Taylor Morgan",
            "tier": "standard",
            "locale": "en-US",
            "contact": "taylor@example.com",
        },
        "business_contexts": [
            {
                "type": "invoice",
                "label": "Invoice INV-1001",
                "source": "billing",
                "source_reference": "INV-1001",
                "status": "paid",
                "fields": {"amount": "125.00", "currency": "USD"},
                "captured_at": "2026-07-28T12:00:00Z",
                "freshness": "current",
                "checked_at": "2026-07-28T12:00:00Z",
            }
        ],
    }


def test_case_webhook_maps_external_identity_to_stable_internal_ids() -> None:
    event = SignedCaseWebhookEvent.model_validate(_payload())

    first = event.to_case_create(organization_id="ORG-0001")
    second = event.to_case_create(organization_id="ORG-0001")
    other_tenant = event.to_case_create(organization_id="ORG-0002")

    assert first.public_id == second.public_id
    assert first.public_id.startswith("CS-WH-")
    assert first.source_id == "signed-webhook:helpdesk:case-1001"
    assert first.business_contexts[0].public_id.startswith("CTX-WH-")
    assert other_tenant.public_id != first.public_id
