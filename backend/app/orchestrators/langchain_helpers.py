"""LangChain prompt and parsing helpers for portable narrative adapters.

The deterministic decision engine remains authoritative. These helpers only shape
the minimized control record and validate narrative wording returned by a model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

    from app.models.openai_decision import DecisionNarrative


class DecisionNarrativePromptTooLarge(ValueError):
    """Raised before a narrative control record can reach a model."""


class DecisionNarrativeParseError(ValueError):
    """Raised when model text does not satisfy the narrative contract."""


def build_decision_narrative_messages(
    control_record: Mapping[str, object],
) -> tuple[BaseMessage, ...]:
    """Render provider-neutral messages with the authoritative output schema."""
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    from app.models.openai_decision import (
        OPENAI_DECISION_INSTRUCTIONS,
        OPENAI_DECISION_MAX_INPUT_CHARS,
        DecisionNarrative,
    )

    serialized_record = json.dumps(
        control_record,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    if len(serialized_record) > OPENAI_DECISION_MAX_INPUT_CHARS:
        raise DecisionNarrativePromptTooLarge(
            "Decision narrative input exceeded the configured safety limit."
        )

    parser: PydanticOutputParser[DecisionNarrative] = PydanticOutputParser(
        pydantic_object=DecisionNarrative
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "{instructions}\n\n{format_instructions}",
            ),
            (
                "human",
                "Server-generated control record:\n{control_record}",
            ),
        ]
    )
    prompt_value = prompt.invoke(
        {
            "instructions": OPENAI_DECISION_INSTRUCTIONS,
            "format_instructions": parser.get_format_instructions(),
            "control_record": serialized_record,
        }
    )
    return tuple(prompt_value.to_messages())


def parse_decision_narrative(raw_output: str) -> DecisionNarrative:
    """Parse model text through LangChain while preserving the Pydantic contract."""
    from langchain_core.exceptions import OutputParserException
    from langchain_core.output_parsers import PydanticOutputParser

    from app.models.openai_decision import DecisionNarrative

    parser: PydanticOutputParser[DecisionNarrative] = PydanticOutputParser(
        pydantic_object=DecisionNarrative
    )
    try:
        return parser.parse(raw_output)
    except OutputParserException as exc:
        raise DecisionNarrativeParseError(
            "Decision narrative output did not satisfy the structured contract."
        ) from exc
