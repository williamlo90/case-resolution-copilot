from app.domain.proposals import IntentClassification
from app.models.gateway import ClassificationRequest


class DeterministicModelGateway:
    provider_name = "deterministic"
    model_version = "rules-v1"

    def classify(self, request: ClassificationRequest) -> IntentClassification:
        normalized = request.customer_message.lower()
        category = "unknown"
        if any(term in normalized for term in ("charged", "charge", "invoice", "billing")):
            category = "billing"
        elif any(term in normalized for term in ("login", "access", "locked", "password")):
            category = "account_access"
        elif any(term in normalized for term in ("cancel", "subscription", "renewal")):
            category = "cancellation"
        elif any(term in normalized for term in ("privacy", "personal data", "data leak")):
            category = "privacy"
        elif any(term in normalized for term in ("complaint", "unhappy", "poor service")):
            category = "service_complaint"
        return IntentClassification(
            intent="support_escalation", case_category=category, confidence=1.0
        )
