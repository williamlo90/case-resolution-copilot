import argparse
from pathlib import Path

from app.evaluation.case_resolution.runner import (
    generate_observations,
    score_observations,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--run-id", required=True)
    generate.add_argument("--case-id", action="append", default=[])
    generate.add_argument("--repeats", type=int, default=1)
    generate.add_argument("--full", action="store_true")
    generate.add_argument("--acknowledge-isolated-run", action="store_true")
    score = subparsers.add_parser("score")
    score.add_argument("--run-id", required=True)
    arguments = parser.parse_args()

    backend_root = Path(__file__).resolve().parents[1]
    benchmark_root = backend_root / "evaluations" / "case_resolution_v1"
    output_root = backend_root / ".benchmark-data" / "case_resolution_v1"
    if arguments.command == "generate":
        case_ids = tuple(arguments.case_id)
        repeats = arguments.repeats
        if arguments.full:
            if not arguments.acknowledge_isolated_run:
                parser.error("Full 20-observation execution requires --acknowledge-isolated-run.")
            case_ids = tuple(f"CRV1-{index:03d}" for index in range(1, 11))
            repeats = 2
        suite = generate_observations(
            benchmark_root=benchmark_root,
            output_root=output_root,
            run_id=arguments.run_id,
            case_ids=case_ids,
            repeats=repeats,
        )
        print(
            f"status=generated run={arguments.run_id} "
            f"observations={len(suite.observations)} mode={suite.execution_mode}"
        )
        return
    report = score_observations(
        benchmark_root=benchmark_root,
        output_root=output_root,
        run_id=arguments.run_id,
    )
    print(
        f"status=scored run={arguments.run_id} complete={str(report.complete_run).lower()} "
        f"observations={report.metrics.observation_count} "
        f"deterministic_pass_rate={report.metrics.deterministic_pass_rate:.3f}"
    )


if __name__ == "__main__":
    main()
