"""Owner-scoped synthetic workspaces for the authenticated V2 walkthrough."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.errors import AppError
from app.domain.identity import ROLE_PERMISSIONS, ActorContext, ActorKind, MemberRole
from app.domain.policies import PolicySourceKind
from app.integrations.connection_seed import deterministic_connection_seeds
from app.integrations.durable_demo_gateway import DurableDemoGateway
from app.persistence.case_repository import CaseRepository
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database
from app.persistence.models import AuditEventModel, MembershipModel, OrganizationModel
from app.persistence.policy_repository import PolicyRepository
from app.persistence.settings_repository import OrganizationSettingsRepository
from app.services.policy_service import PolicyService
from app.services.v2_demo_fixtures import (
    SCENARIOS,
    applicability,
    case_fixture,
    policy_text,
    publish_draft,
)

type DemoRole = Literal["specialist", "reviewer", "policy_manager"]

DEMO_ROLES: dict[DemoRole, tuple[str, MemberRole, str]] = {
    "specialist": ("USR-DEMO-SPECIALIST", MemberRole.SPECIALIST, "Simulated specialist"),
    "reviewer": ("USR-DEMO-REVIEWER", MemberRole.ADMINISTRATOR, "Simulated reviewer"),
    "policy_manager": ("USR-DEMO-POLICY", MemberRole.ADMINISTRATOR, "Simulated policy manager"),
}


def require_demo_admin(actor: ActorContext) -> None:
    if actor.kind is not ActorKind.MEMBER or actor.role is not MemberRole.ADMINISTRATOR:
        raise AppError(
            code="demo_admin_required", message="An administrator is required.", status_code=403
        )


def demo_actor(owner: ActorContext, organization_id: str, role: DemoRole) -> ActorContext:
    public_id, member_role, name = DEMO_ROLES[role]
    return ActorContext(
        actor_id=public_id,
        organization_id=organization_id,
        name=name,
        kind=ActorKind.MEMBER,
        role=member_role,
        permissions=ROLE_PERMISSIONS[member_role],
        authentication_mode=owner.authentication_mode,
    )


class V2DemoSessions:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _owned(self, session: Session, owner: ActorContext, session_id: str) -> AuditEventModel:
        require_demo_admin(owner)
        event = session.scalar(
            select(AuditEventModel)
            .join(OrganizationModel, AuditEventModel.organization_id == OrganizationModel.id)
            .where(
                OrganizationModel.public_id == owner.organization_id,
                AuditEventModel.event_type == "demo.session_created",
                AuditEventModel.subject_id == session_id,
                AuditEventModel.actor_id == owner.actor_id,
            )
        )
        if event is None:
            raise AppError(
                code="demo_not_found", message="Demo session not found.", status_code=404
            )
        return event

    def get(self, owner: ActorContext, session_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            return dict(self._owned(session, owner, session_id).data)

    def list_owned(self, owner: ActorContext) -> list[dict[str, Any]]:
        require_demo_admin(owner)
        with self.database.session() as session:
            return [
                dict(e.data)
                for e in session.scalars(
                    select(AuditEventModel)
                    .join(
                        OrganizationModel, AuditEventModel.organization_id == OrganizationModel.id
                    )
                    .where(
                        OrganizationModel.public_id == owner.organization_id,
                        AuditEventModel.event_type == "demo.session_created",
                        AuditEventModel.actor_id == owner.actor_id,
                    )
                    .order_by(AuditEventModel.occurred_at.desc())
                    .limit(20)
                )
            ]

    def create(
        self, owner: ActorContext, scenario: str, command_id: str, correlation_id: str
    ) -> dict[str, Any]:
        require_demo_admin(owner)
        if scenario not in SCENARIOS:
            raise AppError(
                code="demo_scenario_invalid", message="Choose a V2 scenario.", status_code=422
            )
        with self.database.session() as session:
            root = session.scalar(
                select(OrganizationModel).where(
                    OrganizationModel.public_id == owner.organization_id
                )
            )
            if root is None:
                raise AppError(
                    code="demo_workspace_missing", message="Workspace not found.", status_code=404
                )
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"v2-demo-owner:{root.id}:{owner.actor_id}"},
            )
            previous = list(
                session.scalars(
                    select(AuditEventModel).where(
                        AuditEventModel.organization_id == root.id,
                        AuditEventModel.event_type == "demo.session_created",
                        AuditEventModel.actor_id == owner.actor_id,
                        AuditEventModel.occurred_at >= datetime.now(UTC) - timedelta(days=1),
                    )
                )
            )
            for event in previous:
                if event.data["command_id"] == command_id:
                    if event.data["scenario"] != scenario:
                        raise AppError(
                            code="demo_command_conflict",
                            message="Creation key already used.",
                            status_code=409,
                        )
                    return dict(event.data)
            if len(previous) >= 20:
                raise AppError(
                    code="demo_daily_limit",
                    message="Resume an existing session; daily demo limit reached.",
                    status_code=429,
                )
            token = uuid4().hex[:16].upper()
            organization = OrganizationModel(
                public_id=f"ORG-DEMO-{token}",
                name=f"Synthetic V2 demo {token}",
                slug=f"v2-demo-{token.lower()}",
            )
            session.add(organization)
            session.flush()
            for role, (public_id, member_role, name) in DEMO_ROLES.items():
                session.add(
                    MembershipModel(
                        organization_id=organization.id,
                        public_id=public_id,
                        subject_id=f"demo-only:{token}:{role}",
                        name=name,
                        email=f"{role}@example.com",
                        role=member_role.value,
                        status="active",
                    )
                )
            session.flush()
            OrganizationSettingsRepository(session).ensure_defaults(
                organization_public_id=organization.public_id
            )
            for connection in deterministic_connection_seeds():
                ConnectionRepository(session).seed(
                    organization_public_id=organization.public_id,
                    command=connection,
                    correlation_id=correlation_id,
                )
            manager = demo_actor(owner, organization.public_id, "policy_manager")
            policy = PolicyService(PolicyRepository(session))
            draft = policy.create_policy(
                actor=manager,
                title="Course fee refund",
                description="Synthetic V2 refund authority.",
                source_kind=PolicySourceKind.MANUAL,
                source_name="V2 synthetic SOP",
                source_text=policy_text(),
                applicability=applicability(),
                effective_from=None,
                effective_to=None,
                public_id=f"POL-DEMO-{token}",
                correlation_id=correlation_id,
            )
            publish_draft(policy, draft, manager, correlation_id)
            command = case_fixture(token)
            CaseRepository(session).seed_case(
                organization_public_id=organization.public_id,
                command=command,
                correlation_id=correlation_id,
            )
            data = {
                "session_id": f"VD-{token}",
                "scenario": scenario,
                "command_id": command_id,
                "organization_id": organization.public_id,
                "organization_uuid": str(organization.id),
                "case_id": command.public_id,
                "policy_id": draft.policy.public_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
            session.add(
                AuditEventModel(
                    organization_id=organization.id,
                    event_type="demo.target_initialized",
                    actor_type="system",
                    subject_type="synthetic_target",
                    subject_id=f"COURSE-{token}",
                    summary="Initialized an isolated synthetic ledger; no external payment.",
                    data={
                        "objects": {
                            f"COURSE-{token}": {
                                "owner": f"CUSTOMER-{token}",
                                "currency": "USD",
                                "credited_minor": "0",
                            }
                        }
                    },
                    correlation_id=correlation_id,
                )
            )
            session.add(
                AuditEventModel(
                    organization_id=root.id,
                    event_type="demo.session_created",
                    actor_type="member",
                    actor_id=owner.actor_id,
                    subject_type="v2_demo",
                    subject_id=data["session_id"],
                    summary="Created an owner-scoped synthetic V2 walkthrough.",
                    data=data,
                    correlation_id=correlation_id,
                )
            )
            return data

    def gateway(self, data: dict[str, Any]) -> DurableDemoGateway:
        return DurableDemoGateway(
            self.database,
            UUID(data["organization_uuid"]),
            timeout_after_commit=data["scenario"] == "timeout_recovery",
        )

    def record_command(
        self,
        owner: ActorContext,
        data: dict[str, Any],
        role: DemoRole,
        command: str,
        outcome: str,
        correlation_id: str,
    ) -> None:
        with self.database.session() as session:
            event = self._owned(session, owner, data["session_id"])
            session.add(
                AuditEventModel(
                    organization_id=event.organization_id,
                    event_type="demo.command_observed",
                    actor_type="member",
                    actor_id=owner.actor_id,
                    subject_type="v2_demo",
                    subject_id=data["session_id"],
                    summary=f"Demo {command}: {outcome}.",
                    data={"simulated_role": role, "command": command, "outcome": outcome},
                    correlation_id=correlation_id,
                )
            )

    def observations(self, owner: ActorContext, session_id: str) -> list[dict[str, Any]]:
        with self.database.session() as session:
            event = self._owned(session, owner, session_id)
            return [
                dict(e.data, at=e.occurred_at.isoformat())
                for e in session.scalars(
                    select(AuditEventModel)
                    .where(
                        AuditEventModel.organization_id == event.organization_id,
                        AuditEventModel.subject_id == session_id,
                        AuditEventModel.event_type == "demo.command_observed",
                    )
                    .order_by(AuditEventModel.occurred_at)
                    .limit(100)
                )
            ]
