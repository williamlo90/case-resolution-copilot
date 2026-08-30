import asyncio
import json

import pytest

from app.models.openai_decision import OPENAI_DECISION_MAX_INPUT_CHARS, DecisionNarrative
from app.orchestrators.autogen_adapter import AutoGenPrototypeAdapter
from app.orchestrators.crewai_adapter import CrewAIPrototypeAdapter
from app.orchestrators.prototype_support import PrototypeExecutionError


def _record() -> dict[str, object]:
    return {
        "facts": ["A duplicate settled payment is verified."],
        "approval_required": True,
        "proposed_outcome": "Reverse the duplicate after approval.",
    }


def _narrative() -> DecisionNarrative:
    return DecisionNarrative(
        rationale="The verified records support a correction proposal.",
        uncertainty="A reviewer must still approve the financial action.",
        response_subject="Update on your billing case",
        response_body="We prepared a correction for review; no action has happened yet.",
    )


def test_crewai_prototype_is_explicit_bounded_and_contract_validated() -> None:
    observed: dict[str, str] = {}

    def runner(record: str, api_key: str, model: str, timeout_seconds: float) -> object:
        observed.update(record=record, api_key=api_key, model=model)
        assert timeout_seconds == 30
        return _narrative().model_dump()

    adapter = CrewAIPrototypeAdapter(api_key="test-key", model="test-model", runner=runner)

    assert adapter.run(_record()) == _narrative()
    assert json.loads(observed["record"]) == _record()
    assert observed["api_key"] == "test-key"
    assert adapter.descriptor.default_runtime is False
    assert adapter.descriptor.kind == "prototype"


def test_autogen_prototype_is_explicit_bounded_and_contract_validated() -> None:
    async def runner(record: str, api_key: str, model: str) -> object:
        assert json.loads(record) == _record()
        assert api_key == "test-key"
        assert model == "test-model"
        return _narrative()

    adapter = AutoGenPrototypeAdapter(api_key="test-key", model="test-model", runner=runner)

    assert asyncio.run(adapter.run(_record())) == _narrative()
    assert adapter.descriptor.default_runtime is False
    assert adapter.descriptor.kind == "prototype"


@pytest.mark.parametrize("adapter_kind", ["crewai", "autogen"])
def test_prototypes_reject_oversized_records_before_runner_use(adapter_kind: str) -> None:
    runner_called = False

    if adapter_kind == "crewai":

        def sync_runner(
            record: str,
            api_key: str,
            model: str,
            timeout_seconds: float,
        ) -> object:
            nonlocal runner_called
            runner_called = True
            return _narrative()

        crew_adapter = CrewAIPrototypeAdapter(api_key="test", model="test", runner=sync_runner)
        with pytest.raises(PrototypeExecutionError, match="safety limit"):
            crew_adapter.run({"facts": ["x" * (OPENAI_DECISION_MAX_INPUT_CHARS + 1)]})
    else:

        async def async_runner(record: str, api_key: str, model: str) -> object:
            nonlocal runner_called
            runner_called = True
            return _narrative()

        autogen_adapter = AutoGenPrototypeAdapter(api_key="test", model="test", runner=async_runner)
        with pytest.raises(PrototypeExecutionError, match="safety limit"):
            asyncio.run(
                autogen_adapter.run({"facts": ["x" * (OPENAI_DECISION_MAX_INPUT_CHARS + 1)]})
            )

    assert runner_called is False


def test_prototypes_reject_output_outside_shared_contract() -> None:
    adapter = CrewAIPrototypeAdapter(
        api_key="test",
        model="test",
        runner=lambda record, api_key, model, timeout_seconds: {"rationale": "incomplete"},
    )

    with pytest.raises(PrototypeExecutionError, match="narrative contract"):
        adapter.run(_record())


def test_autogen_prototype_has_an_explicit_wall_clock_timeout() -> None:
    async def stalled_runner(record: str, api_key: str, model: str) -> object:
        await asyncio.sleep(0.1)
        return _narrative()

    adapter = AutoGenPrototypeAdapter(
        api_key="test",
        model="test",
        timeout_seconds=0.01,
        runner=stalled_runner,
    )

    with pytest.raises(TimeoutError):
        asyncio.run(adapter.run(_record()))
