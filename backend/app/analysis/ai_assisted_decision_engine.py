import json
from hashlib import sha256

from app.analysis.action_claim_safety import contains_completed_action_claim
from app.analysis.customer_response_safety import customer_response_is_aligned
from app.analysis.deterministic_decision_engine import DecisionEngine
from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import (
    AnalysisCheckpointDraft,
    AnalysisStatus,
    CheckpointStatus,
    DecisionAnalysis,
)
from app.domain.policies import EvidenceRetrievalResult
from app.models.gateway import ModelGatewayError
from app.models.openai_decision import DecisionNarrativeGateway

AI_DECISION_PROMPT_VERSION = "openai-decision-narrative-v2"


class OpenAIAssistedDecisionEngine:
    def __init__(
        self,
        *,
        baseline: DecisionEngine,
        narrative_gateway: DecisionNarrativeGateway,
    ) -> None:
        self._baseline = baseline
        self._narrative_gateway = narrative_gateway
        self.model_version = f"{narrative_gateway.provider_name}:{narrative_gateway.model_version}"
        self.prompt_version = AI_DECISION_PROMPT_VERSION
        self.graph_version = baseline.graph_version
        self.risk_rule_version = baseline.risk_rule_version

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        baseline = self._baseline.analyze(
            workspace=workspace,
            evidence=evidence,
            input_fingerprint=input_fingerprint,
        )
        if baseline.status is not AnalysisStatus.COMPLETED:
            return self._fallback(
                baseline,
                suffix="skipped",
                summary=(
                    "AI drafting was skipped because the governed analysis abstained. "
                    "The deterministic safe response was retained."
                ),
            )

        try:
            narrative = self._narrative_gateway.refine(baseline)
        except ModelGatewayError:
            return self._fallback(
                baseline,
                suffix="fallback",
                summary=(
                    "AI drafting was unavailable. The deterministic decision language "
                    "was retained without changing any control."
                ),
            )
        if contains_completed_action_claim(
            narrative.rationale,
            narrative.uncertainty,
            narrative.response_subject,
            narrative.response_body,
        ):
            return self._fallback(
                baseline,
                suffix="rejected",
                summary=(
                    "AI drafting was rejected because it described a controlled action as "
                    "already complete. The deterministic safe response was retained."
                ),
            )
        if not customer_response_is_aligned(
            baseline,
            subject=narrative.response_subject,
            body=narrative.response_body,
        ):
            return self._fallback(
                baseline,
                suffix="misaligned",
                summary=(
                    "AI drafting was rejected because the customer response did not match "
                    "the governed next step. The deterministic safe response was retained."
                ),
            )

        checkpoint = _ai_checkpoint(
            baseline,
            status=CheckpointStatus.COMPLETED,
            summary=(
                "AI drafted the explanatory language. Server-owned facts, risks, "
                "actions, and approval requirements were preserved."
            ),
            output={
                "rationale": narrative.rationale,
                "uncertainty": narrative.uncertainty,
                "response_subject": narrative.response_subject,
                "response_body": narrative.response_body,
            },
        )
        return baseline.model_copy(
            update={
                "rationale": narrative.rationale,
                "uncertainty": narrative.uncertainty,
                "response_draft": baseline.response_draft.model_copy(
                    update={
                        "subject": narrative.response_subject,
                        "body": narrative.response_body,
                    }
                ),
                "checkpoints": [*baseline.checkpoints, checkpoint],
                "model_version": self.model_version,
                "prompt_version": self.prompt_version,
            }
        )

    def _fallback(
        self,
        baseline: DecisionAnalysis,
        *,
        suffix: str,
        summary: str,
    ) -> DecisionAnalysis:
        checkpoint = _ai_checkpoint(
            baseline,
            status=CheckpointStatus.ABSTAINED,
            summary=summary,
            output={"status": suffix, "retained_model": baseline.model_version},
        )
        return baseline.model_copy(
            update={
                "checkpoints": [*baseline.checkpoints, checkpoint],
                "model_version": f"{self.model_version}:{suffix}",
                "prompt_version": self.prompt_version,
            }
        )


def _ai_checkpoint(
    analysis: DecisionAnalysis,
    *,
    status: CheckpointStatus,
    summary: str,
    output: object,
) -> AnalysisCheckpointDraft:
    return AnalysisCheckpointDraft(
        sequence=len(analysis.checkpoints) + 1,
        step="ai_narrative",
        status=status,
        summary=summary,
        input_fingerprint=analysis.checkpoints[-1].output_fingerprint,
        output_fingerprint=_hash(output),
    )


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
