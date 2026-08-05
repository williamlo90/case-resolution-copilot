import argparse
from pathlib import Path

from app.config import Settings
from app.evaluation.public_benchmark.ai_predictor import OpenAIPublicEvidenceGateway
from app.evaluation.public_benchmark.ai_runner import (
    DEFAULT_AI_RUN_ID,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL_CALL_BUDGET,
    DEFAULT_TIMEOUT_SECONDS,
    generate_ai_predictions,
    score_ai_predictions,
)
from app.evaluation.public_benchmark.setup import DEFAULT_DATA_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded, serial public-evidence model evaluation with checkpointed outputs."
        )
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-id", default=DEFAULT_AI_RUN_ID)
    parser.add_argument(
        "--phase",
        choices=("all", "predict", "score"),
        default="all",
        help="Run input-only prediction, label-aware scoring, or both phases.",
    )
    parser.add_argument(
        "--model-call-budget",
        type=int,
        default=DEFAULT_MODEL_CALL_BUDGET,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    arguments = parser.parse_args()

    if arguments.phase == "score":
        report = score_ai_predictions(
            arguments.data_root,
            run_id=arguments.run_id,
        )
        _print_report(report)
        return

    settings = Settings()
    api_key = settings.openai_secret()
    if settings.model_provider != "openai" or not api_key:
        raise SystemExit(
            "The AI benchmark requires a configured OpenAI provider and local API key."
        )
    gateway = OpenAIPublicEvidenceGateway(
        api_key=api_key,
        model=settings.openai_model,
        timeout_seconds=arguments.timeout_seconds,
        max_output_tokens=arguments.max_output_tokens,
    )
    try:
        manifest = generate_ai_predictions(
            arguments.data_root,
            gateway=gateway,
            run_id=arguments.run_id,
            model_call_budget=arguments.model_call_budget,
        )
    finally:
        gateway.close()
    if arguments.phase == "predict":
        print(
            f"phase=predict status=passed run={manifest.run_id} "
            f"records={manifest.predictions.records} "
            f"model_calls={manifest.model_calls_started} "
            f"predictions_sha256={manifest.predictions.sha256}"
        )
        return
    report = score_ai_predictions(
        arguments.data_root,
        run_id=arguments.run_id,
    )
    _print_report(report)


def _print_report(report: object) -> None:
    from app.evaluation.public_benchmark.ai_models import AIPublicBenchmarkReport

    validated = AIPublicBenchmarkReport.model_validate(report)
    metrics = " ".join(
        (
            f"{suite.suite}_accuracy={suite.accuracy:.3f} "
            f"{suite.suite}_macro_f1={suite.macro_f1:.3f}"
        )
        for suite in validated.suites
    )
    print(
        f"phase=score status=passed run={validated.run_id} "
        f"model_calls={validated.usage.model_calls_started} {metrics}"
    )


if __name__ == "__main__":
    main()
