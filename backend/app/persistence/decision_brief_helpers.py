import json
from hashlib import sha256

from app.domain.decision_briefs import (
    AnalysisStatus,
    CheckpointStatus,
    DecisionAnalysis,
)


def decision_brief_audit_details(analysis: DecisionAnalysis) -> tuple[str, str]:
    if analysis.status is AnalysisStatus.ABSTAINED:
        return (
            "Decision brief paused because usable policy guidance was not available.",
            "abstained",
        )
    ai_checkpoint = next(
        (
            checkpoint
            for checkpoint in analysis.checkpoints
            if checkpoint.step == "ai_narrative"
        ),
        None,
    )
    if ai_checkpoint is None:
        return (
            "Decision brief prepared from current facts and policy evidence.",
            "rules_only",
        )
    if ai_checkpoint.status is CheckpointStatus.COMPLETED:
        return (
            "Decision brief prepared with AI-assisted wording.",
            "ai_assisted",
        )
    return (
        "Decision brief prepared with the built-in backup draft.",
        "verified_fallback",
    )


def stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def hash_value(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
