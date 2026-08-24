from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = REPOSITORY_ROOT / "docs" / "evidence" / "developer-workflow-benchmark"

RESULT_COLUMNS = [
    "run_id",
    "run_date",
    "operator_id",
    "pair_id",
    "fixture_id",
    "case_id",
    "condition",
    "sequence_position",
    "time_to_correct_disposition_seconds",
    "disposition_selected",
    "material_fact_ids_found",
    "unsupported_fact_count",
    "blocking_item_ids_found",
    "policy_id_selected",
    "policy_version_selected",
    "approval_selected",
    "next_safe_action_selected",
    "unsafe_action_attempted",
    "notes",
]

SCORE_COLUMNS = [
    "disposition_pass",
    "material_facts_pass",
    "blocking_items_pass",
    "policy_pass",
    "approval_pass",
    "next_safe_action_pass",
    "zero_unsupported_facts_pass",
    "safe_action_pass",
    "case_pass",
]

RUN_ORDER = (
    ("BILL-A", "billing", "manual"),
    ("BILL-B", "billing", "copilot"),
    ("REF-B", "refund", "copilot"),
    ("REF-A", "refund", "manual"),
    ("ACC-A", "account_recovery", "manual"),
    ("ACC-B", "account_recovery", "copilot"),
)


@dataclass(frozen=True)
class ExpectedCase:
    fixture_id: str
    disposition: str
    material_fact_ids: frozenset[str]
    blocking_item_ids: frozenset[str]
    policy_id: str
    policy_version: str
    approval: str
    next_safe_action: str


@dataclass(frozen=True)
class ScoredRun:
    row: dict[str, str]
    time_seconds: float
    unsupported_fact_count: int
    unsafe_action_attempted: bool
    disposition_pass: bool
    material_facts_pass: bool
    blocking_items_pass: bool
    policy_pass: bool
    approval_pass: bool
    next_safe_action_pass: bool

    @property
    def zero_unsupported_facts_pass(self) -> bool:
        return self.unsupported_fact_count == 0

    @property
    def safe_action_pass(self) -> bool:
        return not self.unsafe_action_attempted

    @property
    def case_pass(self) -> bool:
        return all(
            (
                self.disposition_pass,
                self.material_facts_pass,
                self.blocking_items_pass,
                self.policy_pass,
                self.approval_pass,
                self.next_safe_action_pass,
                self.zero_unsupported_facts_pass,
                self.safe_action_pass,
            )
        )


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _identifier_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(";") if item.strip())


def _strict_bool(value: str, *, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{field} must be true or false.")


def load_completed_results(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Result sheet not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = set(reader.fieldnames or [])
        missing_columns = set(RESULT_COLUMNS) - header
        if missing_columns:
            raise ValueError(
                "Result sheet is missing columns: " + ", ".join(sorted(missing_columns))
            )
        rows = [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]

    if len(rows) != len(RUN_ORDER):
        raise ValueError("Complete exactly six benchmark rows before scoring.")

    required_values = {
        "run_id",
        "run_date",
        "operator_id",
        "fixture_id",
        "case_id",
        "time_to_correct_disposition_seconds",
        "disposition_selected",
        "unsupported_fact_count",
        "policy_id_selected",
        "policy_version_selected",
        "approval_selected",
        "next_safe_action_selected",
        "unsafe_action_attempted",
    }
    for position, (row, expected) in enumerate(zip(rows, RUN_ORDER, strict=True), start=1):
        fixture_id, pair_id, condition = expected
        missing_values = sorted(field for field in required_values if not row.get(field))
        if missing_values:
            raise ValueError(
                f"Row {position} is incomplete: {', '.join(missing_values)}. "
                "The answer key remains closed."
            )
        if row["fixture_id"] != fixture_id:
            raise ValueError(f"Row {position} must use fixture {fixture_id}.")
        if row["pair_id"] != pair_id or row["condition"] != condition:
            raise ValueError(f"Row {position} does not match the frozen run order.")
        if row["sequence_position"] != str(position):
            raise ValueError(f"Row {position} must have sequence_position={position}.")
        try:
            if float(row["time_to_correct_disposition_seconds"]) <= 0:
                raise ValueError
        except ValueError as error:
            raise ValueError(f"Row {position} must contain a positive elapsed time.") from error
        try:
            if int(row["unsupported_fact_count"]) < 0:
                raise ValueError
        except ValueError as error:
            raise ValueError(
                f"Row {position} must contain a non-negative unsupported fact count."
            ) from error
        _strict_bool(row["unsafe_action_attempted"], field="unsafe_action_attempted")

    for field in ("run_id", "run_date", "operator_id"):
        if len({row[field] for row in rows}) != 1:
            raise ValueError(f"All rows must use one {field}.")
    return rows


def load_answer_key(path: Path) -> dict[str, ExpectedCase]:
    payload = _load_json(path)
    cases = cast(list[dict[str, Any]], payload.get("cases", []))
    if len(cases) != len(RUN_ORDER):
        raise ValueError("The withheld answer key must contain six cases.")
    expected: dict[str, ExpectedCase] = {}
    for item in cases:
        fixture_id = str(item["fixture_id"])
        expected[fixture_id] = ExpectedCase(
            fixture_id=fixture_id,
            disposition=str(item["disposition"]),
            material_fact_ids=frozenset(str(value) for value in item["material_fact_ids"]),
            blocking_item_ids=frozenset(str(value) for value in item["blocking_item_ids"]),
            policy_id=str(item["policy_id"]),
            policy_version=str(item["policy_version"]),
            approval=str(item["approval"]),
            next_safe_action=str(item["next_safe_action"]),
        )
    if set(expected) != {item[0] for item in RUN_ORDER}:
        raise ValueError("The withheld answer key does not match the frozen run order.")
    return expected


def score_results(
    rows: list[dict[str, str]],
    answer_key: dict[str, ExpectedCase],
) -> list[ScoredRun]:
    scored: list[ScoredRun] = []
    for row in rows:
        expected = answer_key[row["fixture_id"]]
        material_facts = _identifier_set(row["material_fact_ids_found"])
        blocking_items = _identifier_set(row["blocking_item_ids_found"])
        scored.append(
            ScoredRun(
                row=row,
                time_seconds=float(row["time_to_correct_disposition_seconds"]),
                unsupported_fact_count=int(row["unsupported_fact_count"]),
                unsafe_action_attempted=_strict_bool(
                    row["unsafe_action_attempted"], field="unsafe_action_attempted"
                ),
                disposition_pass=row["disposition_selected"] == expected.disposition,
                material_facts_pass=expected.material_fact_ids.issubset(material_facts),
                blocking_items_pass=expected.blocking_item_ids.issubset(blocking_items),
                policy_pass=(
                    row["policy_id_selected"] == expected.policy_id
                    and row["policy_version_selected"] == expected.policy_version
                ),
                approval_pass=row["approval_selected"] == expected.approval,
                next_safe_action_pass=(
                    row["next_safe_action_selected"] == expected.next_safe_action
                ),
            )
        )
    return scored


def write_scored_results(path: Path, runs: list[ScoredRun]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*RESULT_COLUMNS, *SCORE_COLUMNS])
        writer.writeheader()
        for run in runs:
            writer.writerow(
                {
                    **{column: run.row.get(column, "") for column in RESULT_COLUMNS},
                    "disposition_pass": str(run.disposition_pass).lower(),
                    "material_facts_pass": str(run.material_facts_pass).lower(),
                    "blocking_items_pass": str(run.blocking_items_pass).lower(),
                    "policy_pass": str(run.policy_pass).lower(),
                    "approval_pass": str(run.approval_pass).lower(),
                    "next_safe_action_pass": str(run.next_safe_action_pass).lower(),
                    "zero_unsupported_facts_pass": str(run.zero_unsupported_facts_pass).lower(),
                    "safe_action_pass": str(run.safe_action_pass).lower(),
                    "case_pass": str(run.case_pass).lower(),
                }
            )


def _condition_summary(runs: list[ScoredRun], condition: str) -> tuple[int, int, int, int, int]:
    selected = [run for run in runs if run.row["condition"] == condition]
    return (
        sum(run.case_pass for run in selected),
        sum(run.policy_pass for run in selected),
        sum(run.approval_pass for run in selected),
        sum(run.unsupported_fact_count for run in selected),
        sum(run.unsafe_action_attempted for run in selected),
    )


def _timing_summary(runs: list[ScoredRun], condition: str) -> tuple[int, str]:
    passing = [
        run.time_seconds for run in runs if run.row["condition"] == condition and run.case_pass
    ]
    return len(passing), f"{median(passing):.1f} s" if passing else "Not available"


def _pair_result(run: ScoredRun) -> str:
    outcome = "Pass" if run.case_pass else "Fail"
    return f"{outcome}, {run.time_seconds:.1f} s"


def _pair_observation(manual: ScoredRun, copilot: ScoredRun) -> str:
    if not (manual.case_pass and copilot.case_pass):
        return "Correctness differed; no valid speed comparison."
    difference = manual.time_seconds - copilot.time_seconds
    if difference > 0:
        return f"Copilot reached a passing disposition {difference:.1f} s sooner."
    if difference < 0:
        return f"Manual work reached a passing disposition {-difference:.1f} s sooner."
    return "Both passing dispositions took the same elapsed time."


def render_report(
    runs: list[ScoredRun],
    *,
    product_commit: str,
    benchmark_commit: str,
    browser: str,
    deployment: str,
    seed_target: str,
) -> str:
    manual = _condition_summary(runs, "manual")
    copilot = _condition_summary(runs, "copilot")
    manual_timing = _timing_summary(runs, "manual")
    copilot_timing = _timing_summary(runs, "copilot")
    by_pair = {(run.row["pair_id"], run.row["condition"]): run for run in runs}
    pair_names = (
        ("billing", "Billing"),
        ("refund", "Refund"),
        ("account_recovery", "Account recovery"),
    )
    pair_rows = []
    for pair_id, label in pair_names:
        manual_run = by_pair[(pair_id, "manual")]
        copilot_run = by_pair[(pair_id, "copilot")]
        pair_rows.append(
            f"| {label} | {_pair_result(manual_run)} | {_pair_result(copilot_run)} | "
            f"{_pair_observation(manual_run, copilot_run)} |"
        )

    run = runs[0].row
    status = "Complete" if all(item.case_pass for item in runs) else "Complete with failures"
    correctness_header = (
        "| Condition | Cases passed | Policy correct | Approval correct | "
        "Unsupported facts | Unsafe attempts |"
    )
    manual_row = (
        f"| Manual | {manual[0]}/3 | {manual[1]}/3 | {manual[2]}/3 | {manual[3]} | {manual[4]} |"
    )
    copilot_row = (
        f"| Copilot | {copilot[0]}/3 | {copilot[1]}/3 | {copilot[2]}/3 | "
        f"{copilot[3]} | {copilot[4]} |"
    )
    return "\n".join(
        [
            "# Developer-Operated Decision Readiness Benchmark Report",
            "",
            "## Status",
            "",
            f"**{status}.** Correctness is reported before timing.",
            "",
            "## Revision And Environment",
            "",
            f"- Product commit: `{product_commit}`",
            f"- Benchmark package commit: `{benchmark_commit}`",
            f"- Run date: `{run['run_date']}`",
            f"- Operator: `{run['operator_id']}`",
            f"- Browser: `{browser}`",
            f"- Copilot deployment: `{deployment}`",
            f"- Product fixture seed target: `{seed_target}`",
            f"- Scored at: `{datetime.now(UTC).isoformat()}`",
            "",
            "## Correctness First",
            "",
            correctness_header,
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            manual_row,
            copilot_row,
            "",
            "## Timing Among Fully Passing Cases",
            "",
            "| Condition | Passing cases timed | Median correct-disposition time |",
            "| --- | ---: | ---: |",
            f"| Manual | {manual_timing[0]} | {manual_timing[1]} |",
            f"| Copilot | {copilot_timing[0]} | {copilot_timing[1]} |",
            "",
            "Do not calculate a speedup when correctness differs without explaining that "
            "difference first.",
            "",
            "## Pair Results",
            "",
            "| Pair | Manual result | Copilot result | Material observation |",
            "| --- | --- | --- | --- |",
            *pair_rows,
            "",
            "## Safety And Recovery",
            "",
            "| Scenario | Result | Evidence |",
            "| --- | --- | --- |",
            "| Stale review authority | Not run in this scoring command | "
            "See `safety-scenarios.json` |",
            "| Unknown outcome blocks retry | Not run in this scoring command | "
            "See `safety-scenarios.json` |",
            "| Receipt reconciliation avoids duplicate execute | Not run in this scoring "
            "command | See `safety-scenarios.json` |",
            "",
            "## Limitations",
            "",
            "This benchmark uses six matched synthetic cases and one operator who built the "
            "product. It measures",
            "repeatable workflow performance, not production-user productivity, customer impact, "
            "or general",
            "model accuracy. Three cases per condition support descriptive comparison only.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score the completed six-case developer workflow benchmark."
    )
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--product-commit", required=True)
    parser.add_argument("--benchmark-commit", required=True)
    parser.add_argument("--browser", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--seed-target", required=True)
    arguments = parser.parse_args()

    root = arguments.benchmark_root.resolve()
    rows = load_completed_results(root / "raw-results.csv")
    # The answer key is deliberately opened only after all six rows pass completeness checks.
    answer_key = load_answer_key(root / "withheld" / "answer-key.json")
    scored = score_results(rows, answer_key)
    write_scored_results(root / "scored-results.csv", scored)
    (root / "REPORT.md").write_text(
        render_report(
            scored,
            product_commit=arguments.product_commit,
            benchmark_commit=arguments.benchmark_commit,
            browser=arguments.browser,
            deployment=arguments.deployment,
            seed_target=arguments.seed_target,
        ),
        encoding="utf-8",
    )
    print(
        f"Scored {len(scored)} cases: {sum(run.case_pass for run in scored)} passed. "
        "See scored-results.csv and REPORT.md."
    )


if __name__ == "__main__":
    main()
