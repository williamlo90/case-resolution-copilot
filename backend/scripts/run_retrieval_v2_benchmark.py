from __future__ import annotations

import argparse
from pathlib import Path

from app.config import Settings
from app.evaluation.retrieval_v2_benchmark import run_frozen_retrieval_v2_benchmark
from app.evaluation.retrieval_v2_contract import load_frozen_retrieval_benchmark
from app.persistence.database import Database
from app.retrieval.v2.embeddings import openai_policy_embedding_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen governed RAG V2 benchmark.")
    parser.add_argument(
        "--include-openai",
        action="store_true",
        help="Run eight bounded synthetic query embeddings against the ready OpenAI profile.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-phase4-gate", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required.")
    benchmark_root = Path(__file__).resolve().parents[1] / "evaluations" / "retrieval_v2"
    benchmark = load_frozen_retrieval_benchmark(benchmark_root)
    openai_provider = None
    if args.include_openai:
        api_key = settings.openai_secret()
        if not api_key:
            raise RuntimeError("A configured SUPPORT_COPILOT_OPENAI_API_KEY is required.")
        openai_provider = openai_policy_embedding_provider(
            api_key=api_key,
            model=settings.openai_embedding_model,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    database = Database(settings.database_url)
    try:
        report = run_frozen_retrieval_v2_benchmark(
            database=database,
            benchmark=benchmark,
            openai_provider=openai_provider,
            query_character_limit=settings.policy_query_char_limit,
        )
    finally:
        database.dispose()
        if openai_provider is not None:
            openai_provider.close()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(
        f"phase4_gate_passed={str(report.phase4_gate_passed).lower()} "
        f"live_openai_evaluated={str(report.live_openai_evaluated).lower()} "
        f"cases={report.profiles[0].metrics.cases}"
    )
    for profile in report.profiles:
        metrics = profile.metrics
        print(
            f"profile={profile.profile_key} generation={profile.retrieval_generation} "
            f"gate={str(metrics.gate_passed).lower()} "
            f"recall_at_3={metrics.recall_at_3:.3f} "
            f"mrr={metrics.mean_reciprocal_rank:.3f} "
            f"status_accuracy={metrics.status_accuracy:.3f} "
            f"embedding_calls={metrics.embedding_calls} "
            f"p95_ms={metrics.latency_p95_ms:.3f}"
        )
        if metrics.gate_failures:
            print(f"profile_failures={profile.profile_key}:{','.join(metrics.gate_failures)}")
    if report.phase4_gate_failures:
        print(f"phase4_failures={','.join(report.phase4_gate_failures)}")
    if args.require_phase4_gate and not report.phase4_gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
