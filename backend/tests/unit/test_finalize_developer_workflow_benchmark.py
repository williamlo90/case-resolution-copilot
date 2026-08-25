from scripts.finalize_developer_workflow_benchmark import (
    FixtureIndex,
    PersistedCaseState,
    PersistedPolicy,
    _canonical_action,
    _canonical_blockers,
    score_observable_results,
)
from scripts.score_developer_workflow_benchmark import ExpectedCase


def _row(*, condition: str, approval: str, action: str) -> dict[str, str]:
    return {
        "run_id": "RUN-1",
        "run_date": "2026-08-24",
        "operator_id": "operator",
        "pair_id": "billing",
        "fixture_id": "BILL-B" if condition == "copilot" else "BILL-A",
        "case_id": "CS-BENCH-BILL-B" if condition == "copilot" else "CS-BENCH-BILL-A",
        "condition": condition,
        "sequence_position": "1",
        "time_to_correct_disposition_seconds": "90",
        "disposition_selected": "information_needed",
        "material_fact_ids_found": "INV-1;PAY-1",
        "unsupported_fact_count": "0",
        "blocking_item_ids_found": "second_payment_reference",
        "policy_id_selected": "POL-1008",
        "policy_version_selected": "1",
        "approval_selected": approval,
        "next_safe_action_selected": action,
        "unsafe_action_attempted": "false",
        "notes": "",
    }


def _expected(fixture_id: str) -> ExpectedCase:
    return ExpectedCase(
        fixture_id=fixture_id,
        disposition="information_needed",
        material_fact_ids=frozenset({f"CTX-{fixture_id}-INVOICE", f"CTX-{fixture_id}-PAYMENT"}),
        blocking_item_ids=frozenset({"second-settled-payment-reference"}),
        policy_id="POL-1008",
        policy_version="1",
        approval="none",
        next_safe_action="request_payment_evidence",
    )


def _fixture(fixture_id: str) -> FixtureIndex:
    return FixtureIndex(
        fixture_id=fixture_id,
        reference_by_internal_id={
            f"CTX-{fixture_id}-INVOICE": "INV-1",
            f"CTX-{fixture_id}-PAYMENT": "PAY-1",
        },
    )


def test_normalizes_operator_facing_blockers_and_actions() -> None:
    assert _canonical_blockers("second_payment_reference") == {"second-settled-payment-reference"}
    assert (
        _canonical_action(pair_id="billing", value="ask_for_information")
        == "request_payment_evidence"
    )


def test_scores_visible_references_and_persisted_state() -> None:
    row = _row(condition="copilot", approval="none", action="ask_for_information")
    expected = _expected("BILL-B")
    fixture = _fixture("BILL-B")
    state = PersistedCaseState(
        fixture_id="BILL-B",
        case_id="CS-BENCH-BILL-B",
        disposition="information_needed",
        context_ids=("CTX-BILL-B-INVOICE", "CTX-BILL-B-PAYMENT"),
        blocking_requirements=("second-settled-payment-reference",),
        policies=(
            PersistedPolicy(
                policy_id="POL-1008",
                version=1,
                clause_id="POL-1008-DUPLICATE",
                heading="Duplicate charges",
                citation="POL-1008 v1 / Duplicate charges",
            ),
        ),
        current_retrieval_preview=(
            PersistedPolicy(
                policy_id="POL-1008",
                version=1,
                clause_id="POL-1008-DUPLICATE",
                heading="Duplicate charges",
                citation="POL-1008 v1 / Duplicate charges",
            ),
        ),
        approval_boundary="none",
        routed_reviewer_role=None,
        review_status=None,
        safe_next_action="request_payment_evidence",
        response_status="blocked",
        proposal_version=1,
    )

    scored = score_observable_results(
        [row],
        {"BILL-B": expected},
        {"BILL-B": fixture},
        {"BILL-B": state},
    )

    assert scored[0].workflow_pass


def test_rejects_a_manual_role_and_unsafe_next_step() -> None:
    row = _row(condition="manual", approval="specialist", action="refund the money")
    row["fixture_id"] = "BILL-A"
    row["case_id"] = "CS-BENCH-BILL-A"

    scored = score_observable_results(
        [row],
        {"BILL-A": _expected("BILL-A")},
        {"BILL-A": _fixture("BILL-A")},
        {},
    )

    assert not scored[0].approval_boundary_pass
    assert not scored[0].safe_next_action_pass
    assert not scored[0].workflow_pass
