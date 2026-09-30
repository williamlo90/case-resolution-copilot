from collections import defaultdict
from statistics import median

from app.evaluation.case_resolution.models import (
    CaseResolutionBenchmarkManifest,
    CaseResolutionCaseGrade,
    CaseResolutionEvaluationReport,
    CaseResolutionMetrics,
)

LIMITATIONS = (
    "The benchmark is synthetic and contains only 10 cases.",
    "The sample has limited statistical power.",
    "No LLM judge was executed in deterministic mode.",
    "Escalation accuracy measures decision disposition, not operational escalation execution.",
    "Automated latency is not evidence of human productivity.",
    "This evaluation does not replace controlled human workflow testing.",
)


def build_report(
    *,
    run_id: str,
    manifest: CaseResolutionBenchmarkManifest,
    grades: tuple[CaseResolutionCaseGrade, ...],
) -> CaseResolutionEvaluationReport:
    if not grades:
        raise ValueError("At least one grade is required.")
    escalation = [item.escalation_correct for item in grades if item.escalation_correct is not None]
    latencies = sorted(item.latency_ms for item in grades)
    complete_run = len(grades) == manifest.case_count * manifest.repeats_per_case
    return CaseResolutionEvaluationReport(
        version="case-resolution-report-v1",
        run_id=run_id,
        benchmark_inputs_sha256=manifest.inputs_sha256,
        benchmark_labels_sha256=manifest.labels_sha256,
        complete_run=complete_run,
        grades=grades,
        metrics=CaseResolutionMetrics(
            observation_count=len(grades),
            case_count=len({item.case_id for item in grades}),
            control_state_accuracy=_rate(grades, "control_state_correct"),
            required_evidence_coverage_rate=_rate(grades, "required_evidence_covered"),
            required_policy_retrieval_coverage_rate=_rate(
                grades, "required_policy_retrieval_covered"
            ),
            risk_outcome_pass_rate=_rate(grades, "risk_outcomes_correct"),
            unsupported_claim_rate=sum(bool(item.unsupported_claims) for item in grades)
            / len(grades),
            escalation_accuracy=(sum(escalation) / len(escalation) if escalation else None),
            required_action_pass_rate=_rate(grades, "required_actions_present"),
            forbidden_action_pass_rate=_rate(grades, "forbidden_actions_absent"),
            schema_validity_rate=_rate(grades, "schema_valid"),
            deterministic_pass_rate=_rate(grades, "deterministic_passed"),
            deterministic_critical_failure_count=sum(
                len(item.critical_failures) for item in grades
            ),
            llm_judge_pass_rate=None,
            p50_latency_ms=median(latencies),
            p95_latency_ms=_percentile(latencies, 0.95),
            average_cost_per_run_usd=None,
            run_to_run_consistency=(
                _consistency(grades, expected_repeats=manifest.repeats_per_case)
                if complete_run
                else None
            ),
        ),
        limitations=LIMITATIONS,
    )


def render_markdown(report: CaseResolutionEvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# Case Resolution Copilot - Evaluation V1",
        "",
        "## Methodology",
        "",
        "Frozen synthetic inputs and reviewed gold labels were finalized before execution. "
        "Generation persisted input-only observations; scoring loaded labels afterward. Critical "
        "deterministic failures cannot be overridden by a semantic judge.",
        "",
        "## Aggregate Results",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Complete run | {str(report.complete_run).lower()} |",
        f"| Observations | {metrics.observation_count} |",
        f"| Control-state accuracy | {metrics.control_state_accuracy:.3f} |",
        f"| Required evidence coverage | {metrics.required_evidence_coverage_rate:.3f} |",
        "| Required policy retrieval coverage | "
        f"{metrics.required_policy_retrieval_coverage_rate:.3f} |",
        f"| Risk outcome accuracy | {metrics.risk_outcome_pass_rate:.3f} |",
        f"| Unsupported claim rate | {metrics.unsupported_claim_rate:.3f} |",
        f"| Required action pass rate | {metrics.required_action_pass_rate:.3f} |",
        f"| Forbidden action pass rate | {metrics.forbidden_action_pass_rate:.3f} |",
        f"| Schema validity | {metrics.schema_validity_rate:.3f} |",
        f"| Deterministic pass rate | {metrics.deterministic_pass_rate:.3f} |",
        f"| Critical failure signals | {metrics.deterministic_critical_failure_count} |",
        f"| P50 latency | {metrics.p50_latency_ms:.2f} ms |",
        f"| P95 latency | {metrics.p95_latency_ms:.2f} ms |",
        f"| Escalation disposition accuracy | {metrics.escalation_accuracy:.3f} |"
        if metrics.escalation_accuracy is not None
        else "| Escalation disposition accuracy | not observed |",
        "| LLM judge pass rate | not executed |",
        "| Average model cost | not applicable (deterministic) |",
        "",
        "## Benchmark Composition",
        "",
        "| Category | Cases |",
        "| --- | ---: |",
        "| Common | 3 |",
        "| Missing information | 2 |",
        "| Conflicting evidence or policy | 2 |",
        "| Policy-heavy | 1 |",
        "| Noisy evidence | 1 |",
        "| Adversarial or safety | 1 |",
        "",
        "## Per-Case Results",
        "",
        "| Case | Repeat | Passed | Critical failures |",
        "| --- | ---: | --- | --- |",
    ]
    lines.extend(
        f"| {item.case_id} | {item.repeat_index} | {str(item.deterministic_passed).lower()} | "
        f"{', '.join(item.critical_failures) or 'none'} |"
        for item in report.grades
    )
    failures = [item for item in report.grades if item.critical_failures]
    lines.extend(["", "## Failure Analysis", ""])
    if failures:
        lines.extend(
            f"- `{item.case_id}` repeat {item.repeat_index}: {', '.join(item.critical_failures)}."
            for item in failures
        )
    else:
        lines.append("No deterministic failure was observed in the executed subset.")
    lines.extend(
        [
            "",
            "## Reliability / Variance",
            "",
            (
                f"Run-to-run control consistency: {metrics.run_to_run_consistency:.3f}."
                if metrics.run_to_run_consistency is not None
                else "A complete two-repeat run was not executed; consistency is not reported."
            ),
            "",
        ]
    )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(
        [
            "",
            "## Recommended V2",
            "",
            "Expand to 30-50 independently reviewed cases, add a blind holdout, execute the "
            "persisted review/action lane, and calibrate any semantic judge against human review.",
        ]
    )
    return "\n".join(lines) + "\n"


def _rate(grades: tuple[CaseResolutionCaseGrade, ...], field: str) -> float:
    return sum(bool(getattr(item, field)) for item in grades) / len(grades)


def _percentile(values: list[float], fraction: float) -> float:
    index = max(0, min(len(values) - 1, round((len(values) - 1) * fraction)))
    return values[index]


def _consistency(
    grades: tuple[CaseResolutionCaseGrade, ...],
    *,
    expected_repeats: int,
) -> float:
    by_case: dict[str, list[str | None]] = defaultdict(list)
    for item in grades:
        by_case[item.case_id].append(item.control_fingerprint)
    consistent = sum(
        len(values) == expected_repeats and len(set(values)) == 1
        for values in by_case.values()
    )
    return consistent / len(by_case)
