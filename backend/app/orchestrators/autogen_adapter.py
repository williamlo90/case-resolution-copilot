import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from app.models.openai_decision import DecisionNarrative
from app.orchestrators.base import OrchestratorDescriptor
from app.orchestrators.prototype_support import (
    OptionalOrchestratorUnavailable,
    PrototypeExecutionError,
    serialize_control_record,
    validate_narrative,
)

AutoGenRunner = Callable[[str, str, str], Awaitable[object]]


class AutoGenPrototypeAdapter:
    """Explicit conversational-agent experiment; excluded from production wiring."""

    descriptor = OrchestratorDescriptor(
        name="structured-agent-prototype-v1",
        framework="AutoGen",
        kind="prototype",
        default_runtime=False,
        purpose="Compare a bounded conversational agent with structured output.",
    )

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30,
        runner: AutoGenRunner | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._runner = runner or _run_autogen

    async def run(self, control_record: Mapping[str, object]) -> DecisionNarrative:
        serialized = serialize_control_record(control_record)
        output = await asyncio.wait_for(
            self._runner(serialized, self._api_key, self._model),
            timeout=self._timeout_seconds,
        )
        return validate_narrative(output)


async def _run_autogen(serialized_record: str, api_key: str, model: str) -> object:
    try:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_core.models import ModelFamily
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError as exc:
        raise OptionalOrchestratorUnavailable(
            "AutoGen is optional. Install the isolated prototype requirements to run it."
        ) from exc

    model_client = OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        timeout=30,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": ModelFamily.GPT_5,
            "structured_output": True,
        },
    )
    try:
        agent = AssistantAgent(
            "case_safety_reviewer",
            model_client=model_client,
            system_message=(
                "Create a customer-safe DecisionNarrative from the supplied server-generated "
                "control record. Preserve facts, uncertainty, actions, and approval gates. "
                "Never invent evidence, references, or amounts. Never expose internal IDs. "
                "State that a review-required action remains pending and has not executed."
            ),
            output_content_type=DecisionNarrative,
            reflect_on_tool_use=False,
            max_tool_iterations=1,
        )
        result: Any = await agent.run(
            task=f"Return the structured narrative for this control record:\n{serialized_record}"
        )
        if not result.messages:
            raise PrototypeExecutionError("AutoGen returned no messages.")
        content = result.messages[-1].content
        if not isinstance(content, DecisionNarrative):
            raise PrototypeExecutionError("AutoGen returned no structured narrative.")
        return content
    finally:
        await model_client.close()
