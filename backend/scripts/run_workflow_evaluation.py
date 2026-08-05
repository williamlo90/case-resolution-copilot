from pathlib import Path

from app.evaluation.workflow import evaluate_workflow


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "evaluations" / "workflow"
    result = evaluate_workflow(root / "golden.json", root / "observed.json")
    print(
        f"cases={result.total} passed={result.passed} failed={result.failed} "
        f"evaluator={result.evaluator} evidence_tier={result.evidence_tier}"
    )
    for case in result.cases:
        if case.result == "failed":
            print(f"failed_case={case.id} checks={','.join(case.failed_checks)}")


if __name__ == "__main__":
    main()
