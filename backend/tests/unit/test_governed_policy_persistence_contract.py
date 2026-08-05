from typing import cast

from sqlalchemy import ForeignKeyConstraint, Table, UniqueConstraint

from app.persistence.models import (
    CasePolicyEvidenceModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyModel,
)


def _unique_names(table: Table) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and isinstance(constraint.name, str)
    }


def _foreign_key_columns(table: Table, name: str) -> tuple[str, ...]:
    constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint) and constraint.name == name
    )
    return tuple(column.name for column in constraint.columns)


def test_governed_policy_roots_and_versions_are_tenant_scoped() -> None:
    assert {"uq_policies_org_id", "uq_policies_org_public"} <= _unique_names(
        cast(Table, PolicyModel.__table__)
    )
    assert {
        "uq_governed_versions_org_policy_version",
        "uq_governed_versions_org_policy_id",
        "uq_governed_versions_legacy_version",
    } <= _unique_names(cast(Table, GovernedPolicyVersionModel.__table__))


def test_clause_and_evidence_foreign_keys_bind_exact_tenant_lineage() -> None:
    assert _foreign_key_columns(
        cast(Table, GovernedPolicyClauseModel.__table__),
        "fk_governed_clauses_org_policy_version",
    ) == ("organization_id", "policy_id", "policy_version_id")
    evidence = cast(Table, CasePolicyEvidenceModel.__table__)
    assert _foreign_key_columns(evidence, "fk_case_policy_evidence_org_case") == (
        "organization_id",
        "case_id",
    )
    assert _foreign_key_columns(evidence, "fk_case_policy_evidence_org_clause") == (
        "organization_id",
        "policy_id",
        "policy_version_id",
        "clause_id",
    )


def test_evidence_fingerprint_is_unique_per_case() -> None:
    assert "uq_case_policy_evidence_org_case_fingerprint" in _unique_names(
        cast(Table, CasePolicyEvidenceModel.__table__)
    )
