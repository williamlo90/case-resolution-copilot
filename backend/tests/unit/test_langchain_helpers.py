import json

import pytest

from app.models.openai_decision import OPENAI_DECISION_MAX_INPUT_CHARS, DecisionNarrative
from app.orchestrators.langchain_helpers import (
    DecisionNarrativeParseError,
    DecisionNarrativePromptTooLarge,
    build_decision_narrative_messages,
    parse_decision_narrative,
)


def _control_record() -> dict[str, object]:
    return {
        "proposal_state": "ready_for_review",
        "facts": ["The duplicate payment is verified."],
        "proposed_outcome": "Reverse the duplicate charge after approval.",
        "actions": [
            {
                "type": "reverse_duplicate_charge",
                "review_required": True,
            }
        ],
    }


def _narrative_payload() -> dict[str, str]:
    return {
        "rationale": "Verified payment records support the proposed correction.",
        "uncertainty": "A reviewer must still approve the correction.",
        "response_subject": "Update on your billing case",
        "response_body": (
            "We verified the duplicate payment and prepared a correction for review. "
            "No account change has been made."
        ),
    }


def test_build_messages_combines_safety_instructions_schema_and_control_record() -> None:
    messages = build_decision_narrative_messages(_control_record())

    assert len(messages) == 2
    assert messages[0].type == "system"
    assert "server-owned facts" in str(messages[0].content).lower()
    assert '"response_body"' in str(messages[0].content)
    assert messages[1].type == "human"
    assert '"proposal_state":"ready_for_review"' in str(messages[1].content)
    assert '"review_required":true' in str(messages[1].content)


def test_build_messages_treats_record_braces_as_data_not_template_syntax() -> None:
    messages = build_decision_narrative_messages(
        {"facts": ["Customer supplied literal {reference_code} text."]}
    )

    assert "{reference_code}" in str(messages[1].content)


def test_build_messages_rejects_oversized_control_record_before_model_use() -> None:
    with pytest.raises(DecisionNarrativePromptTooLarge, match="safety limit"):
        build_decision_narrative_messages({"facts": ["x" * (OPENAI_DECISION_MAX_INPUT_CHARS + 1)]})


def test_parse_decision_narrative_returns_existing_domain_contract() -> None:
    result = parse_decision_narrative(json.dumps(_narrative_payload()))

    assert result == DecisionNarrative.model_validate(_narrative_payload())


@pytest.mark.parametrize(
    "payload",
    [
        {"rationale": "Missing required fields"},
        {**_narrative_payload(), "untrusted_extra": "must fail closed"},
    ],
)
def test_parse_decision_narrative_rejects_invalid_or_expanded_records(
    payload: dict[str, str],
) -> None:
    with pytest.raises(DecisionNarrativeParseError, match="structured contract"):
        parse_decision_narrative(json.dumps(payload))
