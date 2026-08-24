import csv
import json
from pathlib import Path

import pytest

from scripts.score_developer_workflow_benchmark import (
    RESULT_COLUMNS,
    RUN_ORDER,
    load_answer_key,
    load_completed_results,
    render_report,
    score_results,
)


def _row(position: int, fixture_id: str, pair_id: str, condition: str) -> dict[str, str]:
    return {
        "run_id": "RUN-1",
        "run_date": "2026-08-24",
        "operator_id": "OP-1",
        "pair_id": pair_id,
        "fixture_id": fixture_id,
        "case_id": f"CS-{fixture_id}",
        "condition": condition,
        "sequence_position": str(position),
        "time_to_correct_disposition_seconds": str(40 + position),
        "disposition_selected": "ready_for_review",
        "material_fact_ids_found": f"FACT-{fixture_id}",
        "unsupported_fact_count": "0",
        "blocking_item_ids_found": f"BLOCK-{fixture_id}",
        "policy_id_selected": "POL-1",
        "policy_version_selected": "2",
        "approval_selected": "supervisor",
        "next_safe_action_selected": "submit_for_review",
        "unsafe_action_attempted": "false",
        "notes": "",
    }


def _write_results(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_answer_key(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "fixture_id": fixture_id,
                        "disposition": "ready_for_review",
                        "material_fact_ids": [f"FACT-{fixture_id}"],
                        "blocking_item_ids": [f"BLOCK-{fixture_id}"],
                        "policy_id": "POL-1",
                        "policy_version": 2,
                        "approval": "supervisor",
                        "next_safe_action": "submit_for_review",
                        "forbidden_actions": ["execute"],
                    }
                    for fixture_id, _, _ in RUN_ORDER
                ]
            }
        ),
        encoding="utf-8",
    )


def test_scores_only_a_complete_frozen_run(tmp_path: Path) -> None:
    rows = [
        _row(position, fixture_id, pair_id, condition)
        for position, (fixture_id, pair_id, condition) in enumerate(RUN_ORDER, start=1)
    ]
    results_path = tmp_path / "raw-results.csv"
    answer_path = tmp_path / "withheld" / "answer-key.json"
    _write_results(results_path, rows)
    _write_answer_key(answer_path)

    scored = score_results(
        load_completed_results(results_path),
        load_answer_key(answer_path),
    )

    assert len(scored) == 6
    assert all(run.case_pass for run in scored)
    report = render_report(
        scored,
        product_commit="abc123",
        benchmark_commit="def456",
        browser="Edge",
        deployment="https://example.test",
        seed_target="non-production-test",
    )
    assert "| Manual | 3/3" in report
    assert "| Copilot | 3/3" in report
    assert "not production-user productivity" in report


def test_rejects_an_incomplete_run_before_answer_key_is_needed(tmp_path: Path) -> None:
    results_path = tmp_path / "raw-results.csv"
    fixture_id, pair_id, condition = RUN_ORDER[0]
    _write_results(results_path, [_row(1, fixture_id, pair_id, condition)])

    with pytest.raises(ValueError, match="exactly six"):
        load_completed_results(results_path)
