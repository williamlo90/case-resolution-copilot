from collections.abc import Callable, Mapping
from typing import Any

from app.models.openai_decision import DecisionNarrative
from app.orchestrators.base import OrchestratorDescriptor
from app.orchestrators.prototype_support import (
    OptionalOrchestratorUnavailable,
    PrototypeExecutionError,
    serialize_control_record,
    validate_narrative,
)

CrewAIRunner = Callable[[str, str, str, float], object]


class CrewAIPrototypeAdapter:
    """Explicit role-based experiment; never selected by the web application."""

    descriptor = OrchestratorDescriptor(
        name="role-review-prototype-v1",
        framework="CrewAI",
        kind="prototype",
        default_runtime=False,
        purpose="Compare role-based analyst and reviewer collaboration.",
    )

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30,
        runner: CrewAIRunner | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._runner = runner or _run_crewai

    def run(self, control_record: Mapping[str, object]) -> DecisionNarrative:
        serialized = serialize_control_record(control_record)
        output = self._runner(
            serialized,
            self._api_key,
            self._model,
            self._timeout_seconds,
        )
        return validate_narrative(output)


def _run_crewai(
    serialized_record: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> object:
    try:
        from crewai import LLM, Agent, Crew, Process, Task
    except ImportError as exc:
        raise OptionalOrchestratorUnavailable(
            "CrewAI is optional. Install the isolated prototype requirements to run it."
        ) from exc

    llm = LLM(model=f"openai/{model}", api_key=api_key)
    analyst = Agent(
        role="Case evidence analyst",
        goal="Draft a cautious narrative from the supplied control record only.",
        backstory="You separate verified facts from uncertainty and never execute actions.",
        llm=llm,
        allow_delegation=False,
        max_iter=3,
        max_execution_time=timeout_seconds,
        verbose=False,
    )
    reviewer = Agent(
        role="Decision safety reviewer",
        goal="Reject unsupported claims and return a customer-safe structured narrative.",
        backstory=(
            "You preserve approval gates and never invent evidence or completed actions. "
            "A proposed refund must be described as pending review and not issued."
        ),
        llm=llm,
        allow_delegation=False,
        max_iter=3,
        max_execution_time=timeout_seconds,
        verbose=False,
    )
    analysis_task = Task(
        description=(
            "Analyze this server-generated control record without changing its facts, risks, "
            f"actions, or approval requirements:\n{serialized_record}"
        ),
        expected_output="A concise draft rationale, uncertainty statement, and response draft.",
        agent=analyst,
    )
    review_task = Task(
        description=(
            "Review the analyst draft against this original control record:\n"
            f"{serialized_record}\n"
            "Remove unsupported claims and return the exact DecisionNarrative schema. "
            "Do not expose internal IDs. "
            "Mention only evidence, references, and amounts present in the control record. "
            "State explicitly that any review-required action remains pending and has not "
            "been executed."
        ),
        expected_output="A validated DecisionNarrative object with four required string fields.",
        agent=reviewer,
        context=[analysis_task],
        output_pydantic=DecisionNarrative,
    )
    crew = Crew(
        agents=[analyst, reviewer],
        tasks=[analysis_task, review_task],
        process=Process.sequential,
        verbose=False,
        memory=False,
        cache=False,
    )
    result: Any = crew.kickoff()
    if result.pydantic is None:
        raise PrototypeExecutionError("CrewAI returned no structured narrative.")
    return result.pydantic
