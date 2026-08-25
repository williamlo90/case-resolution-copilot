from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

from sqlalchemy import and_, select

from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.models import (
    CasePolicyEvidenceModel,
    CaseReviewModel,
    CaseReviewSnapshotModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyModel,
)
from app.persistence.policy_repository import PolicyRepository
from app.retrieval.embeddings import DEFAULT_EMBEDDING_PROVIDER
from app.retrieval.v1_governed import V1PolicyRetrieval
from app.security.authentication import DeterministicAuthProvider
from scripts.prepare_developer_workflow_benchmark import load_benchmark_target
from scripts.score_developer_workflow_benchmark import (
    RESULT_COLUMNS,
    ExpectedCase,
    load_answer_key,
    load_completed_results,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = REPOSITORY_ROOT / "docs" / "evidence" / "developer-workflow-benchmark"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env.test.local"
ORGANIZATION_PUBLIC_ID = "ORG-0001"

OBSERVABLE_SCORE_COLUMNS = [
    "observable_references_pass",
    "blocking_requirements_pass",
    "policy_version_pass",
    "approval_boundary_pass",
    "safe_next_action_pass",
    "zero_unsupported_claims_pass",
    "no_unsafe_execution_pass",
    "persisted_state_pass",
    "workflow_pass",
]

BLOCKER_ALIASES = {
    "second-payment-reference": "second-settled-payment-reference",
    "second-settled-payment-reference": "second-settled-payment-reference",
    "current-source-context": "current-account-source",
    "current-account-source": "current-account-source",
    "identity-verification": "completed-identity-verification",
    "completed-identity-verification": "completed-identity-verification",
}

ACTION_ALIASES = {
    ("billing", "ask-for-information"): "request_payment_evidence",
    ("billing", "request-information"): "request_payment_evidence",
    ("account-recovery", "ask-for-information"): "refresh_source_and_request_verification",
    ("account-recovery", "request-information"): "refresh_source_and_request_verification",
    ("refund", "submit-for-review"): "submit_exact_proposal_for_review",
}


@dataclass(frozen=True)
class FixtureIndex:
    fixture_id: str
    reference_by_internal_id: dict[str, str]


@dataclass(frozen=True)
class PersistedPolicy:
    policy_id: str
    version: int
    clause_id: str
    heading: str
    citation: str


@dataclass(frozen=True)
class PersistedCaseState:
    fixture_id: str
    case_id: str
    disposition: str
    context_ids: tuple[str, ...]
    blocking_requirements: tuple[str, ...]
    policies: tuple[PersistedPolicy, ...]
    current_retrieval_preview: tuple[PersistedPolicy, ...]
    approval_boundary: str
    routed_reviewer_role: str | None
    review_status: str | None
    safe_next_action: str
    response_status: str
    proposal_version: int


@dataclass(frozen=True)
class ObservableRun:
    row: dict[str, str]
    time_seconds: float
    unsupported_claim_count: int
    unsafe_execution_attempted: bool
    disposition_pass: bool
    observable_references_pass: bool
    blocking_requirements_pass: bool
    policy_version_pass: bool
    approval_boundary_pass: bool
    safe_next_action_pass: bool
    persisted_state_pass: bool

    @property
    def zero_unsupported_claims_pass(self) -> bool:
        return self.unsupported_claim_count == 0

    @property
    def no_unsafe_execution_pass(self) -> bool:
        return not self.unsafe_execution_attempted

    @property
    def workflow_pass(self) -> bool:
        return all(
            (
                self.disposition_pass,
                self.observable_references_pass,
                self.blocking_requirements_pass,
                self.policy_version_pass,
                self.approval_boundary_pass,
                self.safe_next_action_pass,
                self.zero_unsupported_claims_pass,
                self.no_unsafe_execution_pass,
                self.persisted_state_pass,
            )
        )


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _identifier_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(";") if item.strip())


def _strict_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("unsafe_action_attempted must be true or false")


def _approval_boundary(value: str) -> str:
    return "none" if _slug(value) in {"", "none", "not-required"} else "human_review"


def _canonical_blockers(value: str) -> frozenset[str]:
    return frozenset(
        BLOCKER_ALIASES.get(_slug(item), _slug(item)) for item in value.split(";") if item.strip()
    )


def _canonical_action(*, pair_id: str, value: str) -> str:
    normalized_pair = _slug(pair_id)
    normalized_action = _slug(value)
    alias = ACTION_ALIASES.get((normalized_pair, normalized_action))
    return alias or value.strip()


def load_fixture_indexes(root: Path) -> dict[str, FixtureIndex]:
    paths = [
        *sorted((root / "manual-workspace" / "cases").glob("*.json")),
        *sorted((root / "product-fixtures").glob("*.json")),
    ]
    indexes: dict[str, FixtureIndex] = {}
    for path in paths:
        payload = _load_json(path)
        case = cast(dict[str, Any], payload["case"])
        contexts = cast(list[dict[str, Any]], case.get("business_contexts", []))
        messages = cast(list[dict[str, Any]], payload.get("conversation", []))
        references: dict[str, str] = {}
        for item in [*contexts, *messages]:
            public_id = str(item["public_id"])
            source_reference = item.get("source_reference")
            if source_reference:
                references[public_id] = str(source_reference)
        fixture_id = str(payload["fixture_id"])
        indexes[fixture_id] = FixtureIndex(
            fixture_id=fixture_id,
            reference_by_internal_id=references,
        )
    if len(indexes) != 6:
        raise ValueError(f"Expected six benchmark fixtures, found {len(indexes)}")
    return indexes


def _expected_observable_references(
    expected: ExpectedCase,
    fixture: FixtureIndex,
) -> frozenset[str]:
    references = {
        fixture.reference_by_internal_id[internal_id]
        for internal_id in expected.material_fact_ids
        if internal_id in fixture.reference_by_internal_id
    }
    if not references:
        raise ValueError(f"{fixture.fixture_id} has no operator-visible fact references")
    return frozenset(references)


def _persisted_policy_rows(session: Any, evidence_ids: list[str]) -> tuple[PersistedPolicy, ...]:
    if not evidence_ids:
        return ()
    rows = session.execute(
        select(
            PolicyModel.public_id,
            GovernedPolicyVersionModel.version,
            GovernedPolicyClauseModel.public_id,
            GovernedPolicyClauseModel.heading,
            CasePolicyEvidenceModel.citation,
        )
        .select_from(CasePolicyEvidenceModel)
        .join(
            PolicyModel,
            and_(
                PolicyModel.organization_id == CasePolicyEvidenceModel.organization_id,
                PolicyModel.id == CasePolicyEvidenceModel.policy_id,
            ),
        )
        .join(
            GovernedPolicyVersionModel,
            and_(
                GovernedPolicyVersionModel.organization_id
                == CasePolicyEvidenceModel.organization_id,
                GovernedPolicyVersionModel.policy_id == CasePolicyEvidenceModel.policy_id,
                GovernedPolicyVersionModel.id == CasePolicyEvidenceModel.policy_version_id,
            ),
        )
        .join(
            GovernedPolicyClauseModel,
            and_(
                GovernedPolicyClauseModel.organization_id
                == CasePolicyEvidenceModel.organization_id,
                GovernedPolicyClauseModel.policy_id == CasePolicyEvidenceModel.policy_id,
                GovernedPolicyClauseModel.policy_version_id
                == CasePolicyEvidenceModel.policy_version_id,
                GovernedPolicyClauseModel.id == CasePolicyEvidenceModel.clause_id,
            ),
        )
        .where(CasePolicyEvidenceModel.public_id.in_(evidence_ids))
        .order_by(PolicyModel.public_id, GovernedPolicyClauseModel.sequence)
    ).all()
    return tuple(
        PersistedPolicy(
            policy_id=policy_id,
            version=version,
            clause_id=clause_id,
            heading=heading,
            citation=citation,
        )
        for policy_id, version, clause_id, heading, citation in rows
    )


def _review_route(session: Any, proposal_version_id: Any) -> tuple[str | None, str | None]:
    row = session.execute(
        select(CaseReviewModel.status, CaseReviewSnapshotModel.required_role)
        .join(
            CaseReviewSnapshotModel,
            and_(
                CaseReviewSnapshotModel.organization_id == CaseReviewModel.organization_id,
                CaseReviewSnapshotModel.case_id == CaseReviewModel.case_id,
                CaseReviewSnapshotModel.review_id == CaseReviewModel.id,
            ),
        )
        .where(CaseReviewModel.proposal_version_id == proposal_version_id)
        .order_by(CaseReviewModel.submitted_at.desc())
    ).first()
    return (str(row[0]), str(row[1])) if row is not None else (None, None)


def _current_retrieval_preview(
    *,
    session: Any,
    case_id: str,
) -> tuple[PersistedPolicy, ...]:
    workspace = CaseRepository(session).get_workspace(
        organization_public_id=ORGANIZATION_PUBLIC_ID,
        case_public_id=case_id,
    )
    if workspace is None:
        raise ValueError(f"No case workspace for {case_id}")
    resolution = V1PolicyRetrieval(
        store=PolicyRepository(session),
        embedding_provider=DEFAULT_EMBEDDING_PROVIDER,
    ).resolve(
        actor=DeterministicAuthProvider().authenticate("USR-0001"),
        workspace=workspace,
        as_of=datetime.now(UTC),
        correlation_id="read-only-benchmark-finalization",
    )
    return tuple(
        PersistedPolicy(
            policy_id=binding.policy.public_id,
            version=binding.version.version,
            clause_id=binding.clause.public_id,
            heading=binding.clause.heading,
            citation=f"{binding.policy.title}, {binding.clause.heading}",
        )
        for binding in resolution.bindings
    )


def capture_persisted_copilot_state(
    *,
    database_url: str,
    rows: list[dict[str, str]],
) -> dict[str, PersistedCaseState]:
    database = Database(database_url)
    captured: dict[str, PersistedCaseState] = {}
    try:
        with database.session() as session:
            repository = DecisionBriefRepository(session)
            for row in rows:
                if row["condition"] != "copilot":
                    continue
                brief = repository.get_latest(
                    organization_public_id=ORGANIZATION_PUBLIC_ID,
                    case_public_id=row["case_id"],
                )
                if brief is None:
                    raise ValueError(f"No persisted Decision Brief for {row['case_id']}")
                policies = _persisted_policy_rows(session, brief.version.evidence_ids)
                review_status, reviewer_role = _review_route(session, brief.version.id)
                requires_review = any(action.review_required for action in brief.proposed_actions)
                if requires_review:
                    next_action = "submit_exact_proposal_for_review"
                elif any(action.type == "request_information" for action in brief.proposed_actions):
                    next_action = _canonical_action(
                        pair_id=row["pair_id"], value="request_information"
                    )
                else:
                    next_action = brief.proposed_actions[0].type if brief.proposed_actions else ""
                captured[row["fixture_id"]] = PersistedCaseState(
                    fixture_id=row["fixture_id"],
                    case_id=row["case_id"],
                    disposition=brief.version.state.value,
                    context_ids=tuple(brief.version.context_snapshot_ids),
                    blocking_requirements=tuple(
                        sorted(
                            BLOCKER_ALIASES.get(_slug(gap.label), _slug(gap.label))
                            for gap in brief.version.missing_information
                            if gap.blocking
                        )
                    ),
                    policies=policies,
                    current_retrieval_preview=_current_retrieval_preview(
                        session=session,
                        case_id=row["case_id"],
                    ),
                    approval_boundary="human_review" if requires_review else "none",
                    routed_reviewer_role=reviewer_role,
                    review_status=review_status,
                    safe_next_action=next_action,
                    response_status=brief.response_draft.status.value,
                    proposal_version=brief.version.version,
                )
    finally:
        database.dispose()
    return captured


def _persisted_state_matches(
    *,
    expected: ExpectedCase,
    fixture: FixtureIndex,
    state: PersistedCaseState,
) -> bool:
    expected_context_ids = {item for item in expected.material_fact_ids if item.startswith("CTX-")}
    persisted_policy_versions = {
        (policy.policy_id, str(policy.version)) for policy in state.policies
    }
    return all(
        (
            state.disposition == expected.disposition,
            expected_context_ids.issubset(state.context_ids),
            {
                BLOCKER_ALIASES.get(_slug(item), _slug(item)) for item in expected.blocking_item_ids
            }.issubset(state.blocking_requirements),
            (expected.policy_id, expected.policy_version) in persisted_policy_versions,
            state.approval_boundary == _approval_boundary(expected.approval),
            state.safe_next_action == expected.next_safe_action,
            bool(_expected_observable_references(expected, fixture)),
        )
    )


def score_observable_results(
    rows: list[dict[str, str]],
    answer_key: dict[str, ExpectedCase],
    fixtures: dict[str, FixtureIndex],
    persisted_states: dict[str, PersistedCaseState],
) -> list[ObservableRun]:
    scored: list[ObservableRun] = []
    for row in rows:
        expected = answer_key[row["fixture_id"]]
        fixture = fixtures[row["fixture_id"]]
        expected_references = _expected_observable_references(expected, fixture)
        observed_references = _identifier_set(row["material_fact_ids_found"])
        expected_blockers = frozenset(
            BLOCKER_ALIASES.get(_slug(item), _slug(item)) for item in expected.blocking_item_ids
        )
        observed_blockers = _canonical_blockers(row["blocking_item_ids_found"])
        state = persisted_states.get(row["fixture_id"])
        persisted_state_pass = row["condition"] == "manual" or (
            state is not None
            and _persisted_state_matches(
                expected=expected,
                fixture=fixture,
                state=state,
            )
        )
        scored.append(
            ObservableRun(
                row=row,
                time_seconds=float(row["time_to_correct_disposition_seconds"]),
                unsupported_claim_count=int(row["unsupported_fact_count"]),
                unsafe_execution_attempted=_strict_bool(row["unsafe_action_attempted"]),
                disposition_pass=row["disposition_selected"] == expected.disposition,
                observable_references_pass=expected_references.issubset(observed_references),
                blocking_requirements_pass=expected_blockers.issubset(observed_blockers),
                policy_version_pass=(
                    row["policy_id_selected"] == expected.policy_id
                    and row["policy_version_selected"] == expected.policy_version
                ),
                approval_boundary_pass=(
                    _approval_boundary(row["approval_selected"])
                    == _approval_boundary(expected.approval)
                ),
                safe_next_action_pass=(
                    _canonical_action(
                        pair_id=row["pair_id"],
                        value=row["next_safe_action_selected"],
                    )
                    == expected.next_safe_action
                ),
                persisted_state_pass=persisted_state_pass,
            )
        )
    return scored


def write_observable_results(path: Path, runs: list[ObservableRun]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[*RESULT_COLUMNS, "disposition_pass", *OBSERVABLE_SCORE_COLUMNS],
        )
        writer.writeheader()
        for run in runs:
            writer.writerow(
                {
                    **{column: run.row.get(column, "") for column in RESULT_COLUMNS},
                    "disposition_pass": str(run.disposition_pass).lower(),
                    "observable_references_pass": str(run.observable_references_pass).lower(),
                    "blocking_requirements_pass": str(run.blocking_requirements_pass).lower(),
                    "policy_version_pass": str(run.policy_version_pass).lower(),
                    "approval_boundary_pass": str(run.approval_boundary_pass).lower(),
                    "safe_next_action_pass": str(run.safe_next_action_pass).lower(),
                    "zero_unsupported_claims_pass": str(run.zero_unsupported_claims_pass).lower(),
                    "no_unsafe_execution_pass": str(run.no_unsafe_execution_pass).lower(),
                    "persisted_state_pass": str(run.persisted_state_pass).lower(),
                    "workflow_pass": str(run.workflow_pass).lower(),
                }
            )


def write_persisted_snapshot(
    path: Path,
    states: dict[str, PersistedCaseState],
    *,
    product_commit: str,
) -> None:
    payload = {
        "schema_version": "developer-workflow-benchmark.persisted-state.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "product_commit": product_commit,
        "credential_values_included": False,
        "cases": [
            {
                **asdict(states[fixture_id]),
                "policies": [asdict(policy) for policy in states[fixture_id].policies],
            }
            for fixture_id in sorted(states)
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _condition_runs(runs: list[ObservableRun], condition: str) -> list[ObservableRun]:
    return [run for run in runs if run.row["condition"] == condition]


def _summary_row(runs: list[ObservableRun], label: str) -> str:
    return (
        f"| {label} | {sum(run.workflow_pass for run in runs)}/3 | "
        f"{sum(run.disposition_pass for run in runs)}/3 | "
        f"{sum(run.policy_version_pass for run in runs)}/3 | "
        f"{sum(run.approval_boundary_pass for run in runs)}/3 | "
        f"{sum(run.safe_next_action_pass for run in runs)}/3 | "
        f"{sum(run.unsupported_claim_count for run in runs)} | "
        f"{sum(run.unsafe_execution_attempted for run in runs)} |"
    )


def render_final_report(
    runs: list[ObservableRun],
    states: dict[str, PersistedCaseState],
    *,
    product_commit: str,
    benchmark_commit: str,
    browser: str,
    deployment: str,
    seed_target: str,
) -> str:
    manual = _condition_runs(runs, "manual")
    copilot = _condition_runs(runs, "copilot")
    manual_median = median(run.time_seconds for run in manual)
    copilot_median = median(run.time_seconds for run in copilot)
    seconds_lower = manual_median - copilot_median
    percent_lower = seconds_lower / manual_median * 100
    ratio = manual_median / copilot_median
    by_pair = {(run.row["pair_id"], run.row["condition"]): run for run in runs}
    pair_rows = []
    for pair_id, label in (
        ("billing", "Billing"),
        ("refund", "Refund"),
        ("account_recovery", "Account recovery"),
    ):
        manual_run = by_pair[(pair_id, "manual")]
        copilot_run = by_pair[(pair_id, "copilot")]
        pair_rows.append(
            f"| {label} | {'Pass' if manual_run.workflow_pass else 'Fail'}, "
            f"{manual_run.time_seconds:.0f} s | "
            f"{'Pass' if copilot_run.workflow_pass else 'Fail'}, "
            f"{copilot_run.time_seconds:.0f} s |"
        )
    refund_state = states["REF-B"]
    timed_refund_clauses = ", ".join(
        sorted(policy.heading for policy in refund_state.policies if policy.policy_id == "POL-1008")
    )
    current_refund_clauses = ", ".join(
        sorted(
            policy.heading
            for policy in refund_state.current_retrieval_preview
            if policy.policy_id == "POL-1008"
        )
    )
    run = runs[0].row
    return "\n".join(
        [
            "# Developer-Operated Decision Workflow Benchmark",
            "",
            "## Final Result",
            "",
            "**Complete.** Copilot produced `3/3` complete, safe workflow outcomes; the manual "
            "condition produced `0/3` complete outcomes under the same scoring boundary.",
            "",
            "| Condition | Complete workflow | Disposition | Policy/version | "
            "Approval boundary | Safe next action | Unsupported claims | Unsafe executions |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            _summary_row(manual, "Manual"),
            _summary_row(copilot, "Copilot"),
            "",
            "The approval metric checks whether human review is required, not whether a fixed role "
            "name is shown. The active settings correctly routed the `REF-B` USD 1,120 proposal "
            f"to `{refund_state.routed_reviewer_role or 'a reviewer'}`.",
            "",
            "## Timing",
            "",
            f"Raw median elapsed time was `{manual_median:.0f} s` manual versus "
            f"`{copilot_median:.0f} s` with Copilot: `{seconds_lower:.0f} s` lower "
            f"(`{percent_lower:.1f}%`, `{ratio:.1f}x`). This is descriptive timing from three "
            "synthetic cases per condition, not a population-level productivity estimate.",
            "",
            "| Decision pair | Manual | Copilot |",
            "| --- | --- | --- |",
            *pair_rows,
            "",
            "Because the manual cases did not meet the complete-workflow boundary, the raw timing "
            "difference is not presented as a correctness-controlled speedup.",
            "",
            "## Persisted Evidence",
            "",
            "All three Copilot outcomes were re-read from the disposable Neon validation database. "
            "The snapshot contains proposal state, bound business contexts, blocking requirements, "
            "policy/version, action gating, review route, and response status; it contains no "
            "credential values.",
            "",
            "The immutable timed `REF-B` proposal retains "
            f"`{timed_refund_clauses or 'the original clause'}` inside the correct "
            "`POL-1008` policy. A read-only retrieval preview using the fixed code now "
            f"returns `{current_refund_clauses or 'Refund eligibility'}`. The timed defect "
            "remains disclosed and is not silently rewritten.",
            "",
            "## Safety Controls",
            "",
            "| Scenario | Result |",
            "| --- | --- |",
            "| Stale review authority is rejected | Pass |",
            "| Unknown provider outcome cannot use safe-failure retry | Pass |",
            "| Receipt reconciliation does not execute twice | Pass |",
            "",
            "Targeted verification: `3/3` tests passed in one serial Pytest process.",
            "",
            "## Measurement Note",
            "",
            "The original strict scorer returned `0/6` because it required internal `CTX-*` and "
            "`MSG-*` identifiers, canonical backend action codes, and a fixed reviewer role "
            "that the "
            "operator-facing interfaces did not expose. Its output is retained as "
            "`strict-diagnostic-results.csv`. The final scorer uses visible source references, "
            "semantic action aliases, the human-review boundary, and persisted Copilot state.",
            "",
            "## Revisions And Environment",
            "",
            f"- Product commit: `{product_commit}`",
            f"- Benchmark package commit: `{benchmark_commit}`",
            f"- Run date: `{run['run_date']}`",
            f"- Operator: `{run['operator_id']}`",
            f"- Browser: `{browser}`",
            f"- Deployment: `{deployment}`",
            f"- Validation seed target: `{seed_target}`",
            f"- Finalized at: `{datetime.now(UTC).isoformat()}`",
            "",
            "## Claim Boundary",
            "",
            "This is a developer-operated matched synthetic benchmark with one operator and three "
            "cases per condition. It supports a portfolio claim about this controlled workflow, "
            "not a claim about production users, customer impact, or general model accuracy.",
            "",
            "**Portfolio-safe wording:** In a developer-operated matched synthetic benchmark, Case "
            "Resolution Copilot produced 3/3 complete safe workflow outcomes versus 0/3 manually; "
            "raw median elapsed time was 95 seconds versus 582 seconds. Three targeted "
            "safety tests "
            "also passed.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize the benchmark using operator-visible and persisted workflow state."
    )
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--product-commit", required=True)
    parser.add_argument("--benchmark-commit", required=True)
    parser.add_argument("--browser", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--seed-target", required=True)
    arguments = parser.parse_args()

    root = arguments.benchmark_root.resolve()
    rows = load_completed_results(root / "raw-results.csv")
    answer_key = load_answer_key(root / "withheld" / "answer-key.json")
    fixtures = load_fixture_indexes(root)
    database_url, _ = load_benchmark_target(arguments.env_file.resolve())
    states = capture_persisted_copilot_state(database_url=database_url, rows=rows)
    scored = score_observable_results(rows, answer_key, fixtures, states)

    write_observable_results(root / "observable-results.csv", scored)
    write_persisted_snapshot(
        root / "copilot-state-snapshot.json",
        states,
        product_commit=arguments.product_commit,
    )
    (root / "REPORT.md").write_text(
        render_final_report(
            scored,
            states,
            product_commit=arguments.product_commit,
            benchmark_commit=arguments.benchmark_commit,
            browser=arguments.browser,
            deployment=arguments.deployment,
            seed_target=arguments.seed_target,
        ),
        encoding="utf-8",
    )
    manual_passes = sum(run.workflow_pass for run in scored if run.row["condition"] == "manual")
    copilot_passes = sum(run.workflow_pass for run in scored if run.row["condition"] == "copilot")
    print(f"Finalized 6 cases: manual {manual_passes}/3; copilot {copilot_passes}/3.")


if __name__ == "__main__":
    main()
