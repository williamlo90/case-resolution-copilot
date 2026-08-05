from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.evaluation.public_benchmark.ai_generation import (
    AI_PREDICTOR_NAME,
    DEFAULT_AI_RUN_ID,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL_CALL_BUDGET,
    DEFAULT_TIMEOUT_SECONDS,
    PublicEvidenceGateway,
    generate_ai_predictions,
)
from app.evaluation.public_benchmark.ai_models import AIPublicBenchmarkReport
from app.evaluation.public_benchmark.ai_predictor import OpenAIPublicEvidenceGateway
from app.evaluation.public_benchmark.ai_scoring import score_ai_predictions
from app.evaluation.public_benchmark.file_locking import (
    exclusive_run_lock as _exclusive_run_lock,
)

__all__ = [
    "AI_PREDICTOR_NAME",
    "DEFAULT_AI_RUN_ID",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_MODEL_CALL_BUDGET",
    "DEFAULT_TIMEOUT_SECONDS",
    "PublicEvidenceGateway",
    "_exclusive_run_lock",
    "generate_ai_predictions",
    "run_ai_public_benchmark",
    "score_ai_predictions",
]


def run_ai_public_benchmark(
    data_root: Path,
    *,
    gateway: OpenAIPublicEvidenceGateway,
    run_id: str = DEFAULT_AI_RUN_ID,
    model_call_budget: int = DEFAULT_MODEL_CALL_BUDGET,
    clock: Callable[[], datetime] | None = None,
) -> AIPublicBenchmarkReport:
    generate_ai_predictions(
        data_root,
        gateway=gateway,
        run_id=run_id,
        model_call_budget=model_call_budget,
        clock=clock,
    )
    return score_ai_predictions(data_root, run_id=run_id, clock=clock)
