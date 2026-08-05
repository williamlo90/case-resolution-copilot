import argparse
from pathlib import Path
from typing import cast

from app.analysis.ai_assisted_decision_engine import OpenAIAssistedDecisionEngine
from app.analysis.deterministic_decision_engine import (
    DecisionEngine,
    DeterministicDecisionEngine,
)
from app.config import Settings
from app.evaluation.decision_brief_runtime import (
    DEFAULT_DECISION_BRIEF_RUN_ID,
    BoundedNarrativeGateway,
    DecisionBriefExecutionMode,
    run_decision_brief_evaluation,
)
from app.models.openai_decision import OpenAIDecisionNarrativeGateway


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_DECISION_BRIEF_RUN_ID)
    parser.add_argument(
        "--mode",
        choices=("deterministic", "provider"),
        default="provider",
    )
    arguments = parser.parse_args()
    settings = Settings()
    baseline = DeterministicDecisionEngine()
    gateway: OpenAIDecisionNarrativeGateway | None = None
    bounded_gateway: BoundedNarrativeGateway | None = None
    engine: DecisionEngine = baseline
    if arguments.mode == "provider":
        api_key = settings.openai_secret()
        if not api_key:
            raise RuntimeError(
                "SUPPORT_COPILOT_OPENAI_API_KEY is required for provider evaluation."
            )
        gateway = OpenAIDecisionNarrativeGateway(
            api_key=api_key,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=0,
        )
        bounded_gateway = BoundedNarrativeGateway(gateway)
        engine = OpenAIAssistedDecisionEngine(
            baseline=baseline,
            narrative_gateway=bounded_gateway,
        )

    root = Path(__file__).resolve().parents[1] / ".benchmark-data"
    try:
        report = run_decision_brief_evaluation(
            engine=engine,
            output_root=root,
            execution_mode=cast(DecisionBriefExecutionMode, arguments.mode),
            run_id=arguments.run_id,
            provider_counter=bounded_gateway,
        )
    finally:
        if gateway is not None:
            gateway.close()
    print(
        f"run={report.run_id} cases={report.total} passed={report.passed} "
        f"failed={report.failed} provider_calls={report.provider_calls} "
        f"control_preservation={report.control_preservation_rate:.3f}"
    )


if __name__ == "__main__":
    main()
