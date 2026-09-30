from pathlib import Path

from app.evaluation.case_resolution.validation import (
    load_frozen_case_resolution_benchmark,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "evaluations" / "case_resolution_v1"
    benchmark = load_frozen_case_resolution_benchmark(root)
    categories = sorted(
        {
            category.value: sum(
                case.benchmark_category is category for case in benchmark.inputs.cases
            )
            for category in type(benchmark.inputs.cases[0].benchmark_category)
        }.items()
    )
    composition = ",".join(f"{name}={count}" for name, count in categories)
    print(
        "status=passed "
        f"cases={len(benchmark.inputs.cases)} "
        f"labels={len(benchmark.labels.cases)} "
        f"repeats={benchmark.manifest.repeats_per_case} "
        f"composition={composition}"
    )


if __name__ == "__main__":
    main()
