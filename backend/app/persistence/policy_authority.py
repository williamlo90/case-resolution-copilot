"""One authority selection and transaction ordering for publish, approve, and dispatch."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, exists, or_, select, text
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from app.persistence.models import GovernedPolicyVersionModel, PolicyModel


def lock_policy_authority(session: Session, organization_id: UUID) -> None:
    # Transaction-scoped PostgreSQL lock; never held during a remote provider call.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"case-resolution:policy-authority:{organization_id}"},
    )


def selected_version(at: datetime) -> ColumnElement[bool]:
    version = GovernedPolicyVersionModel
    newer = aliased(GovernedPolicyVersionModel)
    eligible = ("published", "scheduled")
    return and_(
        version.immutable.is_(True),
        version.status.in_(eligible),
        or_(version.effective_from.is_(None), version.effective_from <= at),
        or_(version.effective_to.is_(None), version.effective_to > at),
        ~exists(
            select(newer.id).where(
                newer.organization_id == version.organization_id,
                newer.policy_id == version.policy_id,
                newer.version > version.version,
                newer.immutable.is_(True),
                or_(
                    newer.status.in_(eligible),
                    and_(
                        newer.status == "retired",
                        newer.retired_at.is_not(None),
                        or_(
                            newer.effective_from.is_(None), newer.retired_at >= newer.effective_from
                        ),
                    ),
                ),
                or_(newer.effective_from.is_(None), newer.effective_from <= at),
            )
        ),
    )


def is_current_authority(session: Session, version_id: UUID, at: datetime) -> bool:
    head = aliased(GovernedPolicyVersionModel)
    return (
        session.scalar(
            select(GovernedPolicyVersionModel.id)
            .join(PolicyModel, PolicyModel.id == GovernedPolicyVersionModel.policy_id)
            .join(
                head,
                and_(
                    head.policy_id == PolicyModel.id,
                    head.organization_id == PolicyModel.organization_id,
                    head.version == PolicyModel.current_version,
                ),
            )
            .where(GovernedPolicyVersionModel.id == version_id, selected_version(at))
        )
        is not None
    )
