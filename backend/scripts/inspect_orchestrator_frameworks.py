import argparse
import asyncio
import importlib.util
import json
import os
from collections.abc import Sequence
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.orchestrators.autogen_adapter import AutoGenPrototypeAdapter
from app.orchestrators.crewai_adapter import CrewAIPrototypeAdapter
from app.orchestrators.langchain_helpers import build_decision_narrative_messages
from app.orchestrators.langgraph_orchestrator import LangGraphDecisionOrchestrator

PrototypeName = Literal["crewai", "autogen"]


class FrameworkInventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    framework: str
    role: str
    production_default: bool
    dependency_available: bool
    validation: str


class PrototypeRunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    framework: str
    output_contract_valid: bool
    elapsed_ms: float


def framework_inventory() -> list[FrameworkInventoryItem]:
    messages = build_decision_narrative_messages(_control_record())
    if len(messages) != 2:
        raise RuntimeError("The LangChain prompt contract did not produce two messages.")
    return [
        FrameworkInventoryItem(
            framework=LangGraphDecisionOrchestrator.descriptor.framework,
            role="Production decision checkpoint orchestration",
            production_default=True,
            dependency_available=_module_available("langgraph"),
            validation="Default runtime and unit/contract tested",
        ),
        FrameworkInventoryItem(
            framework="LangChain Core",
            role="Prompt templates and schema-format instructions",
            production_default=False,
            dependency_available=_module_available("langchain_core"),
            validation="Prompt builder is used by the optional OpenAI path and unit tested",
        ),
        FrameworkInventoryItem(
            framework="CrewAI",
            role="Optional analyst/reviewer role prototype",
            production_default=False,
            dependency_available=_module_available("crewai"),
            validation="Adapter contract tested; live model run is opt-in",
        ),
        FrameworkInventoryItem(
            framework="AutoGen",
            role="Optional structured conversational-agent prototype",
            production_default=False,
            dependency_available=_module_available("autogen_agentchat"),
            validation="Adapter contract tested; live model run is opt-in",
        ),
    ]


def run_prototype(name: PrototypeName, *, api_key: str, model: str) -> PrototypeRunReport:
    started_at = perf_counter()
    if name == "crewai":
        CrewAIPrototypeAdapter(api_key=api_key, model=model).run(_control_record())
        framework = "CrewAI"
    else:
        asyncio.run(AutoGenPrototypeAdapter(api_key=api_key, model=model).run(_control_record()))
        framework = "AutoGen"
    return PrototypeRunReport(
        framework=framework,
        output_contract_valid=True,
        elapsed_ms=round((perf_counter() - started_at) * 1000, 3),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect orchestrator roles or explicitly run one isolated prototype."
    )
    parser.add_argument("--run-prototype", choices=("crewai", "autogen"))
    parser.add_argument(
        "--model",
        default=os.getenv("SUPPORT_COPILOT_OPENAI_MODEL", "gpt-5.6-luna"),
    )
    args = parser.parse_args(argv)

    payload: dict[str, object] = {
        "frameworks": [row.model_dump(mode="json") for row in framework_inventory()]
    }
    if args.run_prototype:
        api_key = os.getenv("SUPPORT_COPILOT_OPENAI_API_KEY", "")
        if not api_key:
            parser.error(
                "SUPPORT_COPILOT_OPENAI_API_KEY is required for an explicit prototype run."
            )
        payload["prototype_run"] = run_prototype(
            args.run_prototype,
            api_key=api_key,
            model=args.model,
        ).model_dump(mode="json")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _control_record() -> dict[str, object]:
    return {
        "proposal_state": "ready_for_review",
        "facts": ["A duplicate settled payment is verified."],
        "missing_information": [],
        "proposed_outcome": "Reverse the duplicate charge after authorized review.",
        "actions": [
            {
                "type": "reverse_duplicate_charge",
                "review_required": True,
            }
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
