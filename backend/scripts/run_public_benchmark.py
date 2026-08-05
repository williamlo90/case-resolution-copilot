import argparse
from pathlib import Path
from typing import Literal

from app.evaluation.public_benchmark.runner import (
    generate_predictions,
    run_public_benchmark,
    score_predictions,
)
from app.evaluation.public_benchmark.setup import DEFAULT_DATA_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded public benchmark with an input-only deterministic baseline."
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-id", default="deterministic-baseline-v1")
    parser.add_argument(
        "--phase",
        choices=("all", "predict", "score"),
        default="all",
        help="Run both phases, input-only prediction, or label-aware scoring.",
    )
    arguments = parser.parse_args()
    phase: Literal["all", "predict", "score"] = arguments.phase

    if phase == "predict":
        manifest = generate_predictions(
            arguments.data_root,
            run_id=arguments.run_id,
        )
        print(
            f"phase=predict status=passed run={manifest.run_id} "
            f"records={manifest.predictions.records} "
            f"predictions_sha256={manifest.predictions.sha256}"
        )
        return
    if phase == "score":
        report = score_predictions(
            arguments.data_root,
            run_id=arguments.run_id,
        )
    else:
        report = run_public_benchmark(
            arguments.data_root,
            run_id=arguments.run_id,
        )

    metrics = " ".join(
        f"{suite.suite}_accuracy={suite.accuracy:.3f} {suite.suite}_macro_f1={suite.macro_f1:.3f}"
        for suite in report.suites
    )
    print(
        f"phase={phase} status=passed run={report.run_id} "
        f"integrity_checks={len(report.integrity_checks)} {metrics}"
    )


if __name__ == "__main__":
    main()
