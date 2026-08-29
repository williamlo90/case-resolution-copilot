from __future__ import annotations

import argparse
from pathlib import Path

from app.evaluation.wave1_rag_contract import load_wave1_rag_fixture
from app.evaluation.wave1_rag_observability import JsonlRagEventSink
from app.evaluation.wave1_rag_runtime import run_wave1_rag_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the credential-free governed RAG V2 Wave 1 evaluation."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--require-gate", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    fixture = load_wave1_rag_fixture(root / "evaluations" / "wave1_rag" / "fixture.json")
    sink = JsonlRagEventSink(args.events) if args.events else None
    report = run_wave1_rag_evaluation(fixture=fixture, event_sink=sink)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    metrics = report.metrics
    print(
        f"gate_passed={str(metrics.gate_passed).lower()} "
        f"cases={metrics.cases} "
        f"source_hit_at_3={metrics.source_hit_rate_at_3:.3f} "
        f"source_recall_at_3={metrics.source_recall_at_3:.3f} "
        f"status_accuracy={metrics.status_accuracy:.3f} "
        f"p95_ms={metrics.latency_p95_ms:.3f} "
        f"runtime_failures={metrics.runtime_failure_count}"
    )
    for failure in metrics.gate_failures:
        print(f"failure={failure}")
    if args.require_gate and not metrics.gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
