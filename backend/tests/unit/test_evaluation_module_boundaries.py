from pathlib import Path

from app.evaluation.decision_brief_runtime import (
    build_evaluation_evidence,
    build_evaluation_workspace,
    run_decision_brief_evaluation,
)
from app.evaluation.public_benchmark.ai_runner import (
    generate_ai_predictions,
    run_ai_public_benchmark,
    score_ai_predictions,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_ROOT = BACKEND_ROOT / "app" / "evaluation"


def test_evaluation_modules_remain_reviewable() -> None:
    oversized = {
        path.relative_to(BACKEND_ROOT).as_posix(): len(
            path.read_text(encoding="utf-8").splitlines()
        )
        for path in EVALUATION_ROOT.rglob("*.py")
        if len(path.read_text(encoding="utf-8").splitlines()) > 650
    }

    assert oversized == {}


def test_evaluation_facades_preserve_public_entry_points() -> None:
    assert all(
        callable(entry_point)
        for entry_point in (
            build_evaluation_evidence,
            build_evaluation_workspace,
            generate_ai_predictions,
            run_ai_public_benchmark,
            run_decision_brief_evaluation,
            score_ai_predictions,
        )
    )
