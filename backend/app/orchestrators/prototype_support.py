import json
from collections.abc import Mapping

from pydantic import ValidationError

from app.models.openai_decision import (
    OPENAI_DECISION_MAX_INPUT_CHARS,
    DecisionNarrative,
)


class OptionalOrchestratorUnavailable(RuntimeError):
    """Raised when an explicitly requested prototype dependency is unavailable."""


class PrototypeExecutionError(RuntimeError):
    """Raised when an optional framework returns an invalid result."""


def serialize_control_record(control_record: Mapping[str, object]) -> str:
    serialized = json.dumps(
        control_record,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    if len(serialized) > OPENAI_DECISION_MAX_INPUT_CHARS:
        raise PrototypeExecutionError("Prototype input exceeded the configured safety limit.")
    return serialized


def validate_narrative(value: object) -> DecisionNarrative:
    if isinstance(value, DecisionNarrative):
        return value
    try:
        return DecisionNarrative.model_validate(value)
    except ValidationError as exc:
        raise PrototypeExecutionError(
            "Prototype output did not satisfy the decision narrative contract."
        ) from exc
