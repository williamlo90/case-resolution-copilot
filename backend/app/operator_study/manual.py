"""Human-authored proposal transcription. Does not run the recommendation engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import DecisionAnalysis
from app.domain.policies import EvidenceRetrievalResult
from app.evaluation.case_resolution_v2.models import Scenario
from app.evaluation.case_resolution_v2.storage import digest


class ManualEngine:
    model_version = "human-operator"
    prompt_version = "none"
    graph_version = "human-study-2"
    risk_rule_version = "human-study-2"

    def __init__(self, scenario: Scenario, submitted: dict[str, Any]) -> None:
        self.scenario, self.submitted = scenario, submitted

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        del workspace
        value = self.submitted
        picked = set(value.get("evidence_ids", []))
        facts = [
            {
                "id": f"H-{i}-{j}",
                "statement": f"{key.replace('_', ' ').capitalize()}: {item}.",
                "source": f"{row.id} / {row.id}",
                "verified_at": self.scenario.as_of,
            }
            for i, row in enumerate(self.scenario.evidence)
            if row.id in picked
            for j, (key, item) in enumerate(row.facts.items())
        ]
        parameters = {str(key): str(item) for key, item in value.get("parameters", {}).items()}
        amount = Decimal(parameters["amount_minor"]) / 100 if "amount_minor" in parameters else None
        resolving = value["disposition"] == "resolve"
        gaps = [
            {
                "id": f"HG-{i}",
                "label": gap.replace("_", " ").capitalize(),
                "description": "Blocking item identified by the operator.",
                "blocking": True,
            }
            for i, gap in enumerate(value.get("gaps", []))
        ]
        return DecisionAnalysis.model_validate(
            {
                "status": "completed",
                "policy_status": evidence.status,
                "facts": facts,
                "missing_information": gaps,
                "risks": [],
                "outcome": value["reason"],
                "impact_amount": amount,
                "impact_currency": parameters.get("currency"),
                "confidence": "medium",
                "uncertainty": "Human-authored controlled study decision.",
                "rationale": value["reason"],
                "state": "ready_for_review" if resolving else "information_needed",
                "proposed_actions": [
                    {
                        "type": value["action_type"],
                        "label": value["action_type"].replace("_", " "),
                        "parameters": parameters,
                        "impact_amount": amount,
                        "impact_currency": parameters.get("currency"),
                        "expected_outcome": "Verify the selected target change before closure.",
                        "review_required": True,
                    }
                ]
                if resolving
                else [],
                "response_draft": {
                    "subject": "Case update",
                    "body": value["communication"],
                    "status": "ready",
                },
                "checkpoints": [
                    {
                        "sequence": 1,
                        "step": "human_decision",
                        "status": "completed",
                        "summary": "Human input transcribed without automatic recommendation.",
                        "input_fingerprint": input_fingerprint,
                        "output_fingerprint": digest(value),
                    }
                ],
                "risk_rule_version": self.risk_rule_version,
                "model_version": self.model_version,
                "prompt_version": self.prompt_version,
                "graph_version": self.graph_version,
            }
        )
