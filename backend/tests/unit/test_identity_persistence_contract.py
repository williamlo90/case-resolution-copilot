from typing import cast

from sqlalchemy import Table, UniqueConstraint

from app.persistence.models import (
    AuditEventModel,
    InvitationModel,
    MembershipModel,
    OrganizationModel,
)


def _unique_constraint_names(table: Table) -> set[str | None]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and isinstance(constraint.name, str)
    }


def test_identity_tables_define_tenant_scoped_uniqueness() -> None:
    assert "uq_organizations_public_id" in _unique_constraint_names(
        cast(Table, OrganizationModel.__table__)
    )
    assert {
        "uq_memberships_org_public",
        "uq_memberships_org_subject",
        "uq_memberships_org_email",
    } <= _unique_constraint_names(cast(Table, MembershipModel.__table__))
    assert {
        "uq_invitations_org_public",
        "uq_invitations_provider_invitation",
    } <= _unique_constraint_names(cast(Table, InvitationModel.__table__))


def test_generic_audit_can_be_tenant_scoped_without_a_legacy_task() -> None:
    assert AuditEventModel.__table__.c.organization_id.nullable
    assert AuditEventModel.__table__.c.task_id.nullable
    assert not AuditEventModel.__table__.c.correlation_id.nullable
