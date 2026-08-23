import argparse
from datetime import date
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
from app.evaluation.provider_cost import ProviderTokenPricing
from app.models.openai_decision import OpenAIDecisionNarrativeGateway


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_DECISION_BRIEF_RUN_ID)
    parser.add_argument(
        "--mode",
        choices=("deterministic", "provider"),
        default="provider",
    )
    parser.add_argument("--pricing-checked-on")
    parser.add_argument("--pricing-source-url")
    parser.add_argument("--input-usd-per-million", type=float)
    parser.add_argument("--cached-input-usd-per-million", type=float)
    parser.add_argument("--cache-write-input-usd-per-million", type=float)
    parser.add_argument("--output-usd-per-million", type=float)
    arguments = parser.parse_args()
    settings = Settings()
    pricing = _provider_pricing(arguments, model=settings.openai_model, parser=parser)
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
            pricing=pricing,
        )
    finally:
        if gateway is not None:
            gateway.close()
    print(
        f"run={report.run_id} cases={report.total} passed={report.passed} "
        f"failed={report.failed} provider_calls={report.provider_calls} "
        f"control_preservation={report.control_preservation_rate:.3f} "
        f"usage_complete={str(report.provider_cost.usage_complete).lower()} "
        f"total_tokens={report.provider_cost.token_usage.total_tokens} "
        f"total_cost_usd={report.provider_cost.total_cost_usd} "
        f"cost_per_case_usd={report.provider_cost.cost_per_evaluated_case_usd}"
    )


def _provider_pricing(
    arguments: argparse.Namespace,
    *,
    model: str,
    parser: argparse.ArgumentParser,
) -> ProviderTokenPricing | None:
    values = (
        arguments.pricing_checked_on,
        arguments.pricing_source_url,
        arguments.input_usd_per_million,
        arguments.cached_input_usd_per_million,
        arguments.cache_write_input_usd_per_million,
        arguments.output_usd_per_million,
    )
    if not any(value is not None for value in values):
        return None
    if arguments.mode != "provider":
        parser.error("Provider pricing can be used only in provider mode.")
    if not all(value is not None for value in values):
        parser.error("All provider pricing arguments are required together.")
    try:
        checked_on = date.fromisoformat(arguments.pricing_checked_on)
    except ValueError:
        parser.error("--pricing-checked-on must use YYYY-MM-DD.")
    return ProviderTokenPricing(
        model=model,
        checked_on=checked_on,
        source_url=arguments.pricing_source_url,
        input_usd_per_million=arguments.input_usd_per_million,
        cached_input_usd_per_million=arguments.cached_input_usd_per_million,
        cache_write_input_usd_per_million=arguments.cache_write_input_usd_per_million,
        output_usd_per_million=arguments.output_usd_per_million,
    )


if __name__ == "__main__":
    main()
