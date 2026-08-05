from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    ActorMembershipAmbiguous,
    ActorMembershipNotFound,
    ActorOrganizationContext,
    AuthenticationMode,
    InvitationConflict,
    InvitationNotFound,
    InvitationRecord,
    InvitationStatus,
    InvitationVersionConflict,
    InvitedIdentity,
    MemberConflict,
    MemberNotFound,
    MemberRecord,
    MemberRole,
    MemberStatus,
    MemberVersionConflict,
    OrganizationRecord,
)
from app.domain.settings import GeneralSettingsValues, SettingsSection, default_settings
from app.persistence.models import (
    AuditEventModel,
    InvitationModel,
    MembershipModel,
    OrganizationModel,
    OrganizationSettingModel,
)


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _organization_model(self, public_id: str) -> OrganizationModel | None:
        return self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == public_id)
        )

    def get_organization(self, organization_public_id: str) -> OrganizationRecord | None:
        model = self._organization_model(organization_public_id)
        return OrganizationRecord.model_validate(model) if model else None

    def resolve_actor_by_subject(self, subject_id: str) -> ActorContext:
        rows = self._session.execute(
            select(
                MembershipModel,
                OrganizationModel,
                OrganizationSettingModel.configuration,
            )
            .join(
                OrganizationModel,
                OrganizationModel.id == MembershipModel.organization_id,
            )
            .outerjoin(
                OrganizationSettingModel,
                and_(
                    OrganizationSettingModel.organization_id == OrganizationModel.id,
                    OrganizationSettingModel.section == SettingsSection.GENERAL.value,
                ),
            )
            .where(
                MembershipModel.subject_id == subject_id,
                MembershipModel.status == MemberStatus.ACTIVE.value,
            )
            .limit(2)
        ).all()
        if not rows:
            raise ActorMembershipNotFound(
                "The identity is not linked to an active workspace membership."
            )
        if len(rows) > 1:
            raise ActorMembershipAmbiguous(
                "The identity is linked to more than one active workspace."
            )

        member, organization, general_configuration = rows[0]
        fallback = default_settings(
            SettingsSection.GENERAL,
            organization_name=organization.name,
        )
        if not isinstance(fallback, GeneralSettingsValues):
            raise RuntimeError("The default general settings are invalid.")
        try:
            general = GeneralSettingsValues.model_validate(
                general_configuration or fallback.model_dump(mode="json"),
            )
        except ValueError:
            general = fallback
        role = MemberRole(member.role)
        return ActorContext(
            actor_id=member.public_id,
            organization_id=organization.public_id,
            name=member.name,
            kind=ActorKind.MEMBER,
            role=role,
            permissions=ROLE_PERMISSIONS[role],
            authentication_mode=AuthenticationMode.PROVIDER,
            organization=ActorOrganizationContext(
                id=organization.public_id,
                name=organization.name,
                slug=organization.slug,
                version=organization.version,
                locale=general.locale,
                time_zone=general.time_zone,
            ),
        )

    def list_members(self, organization_public_id: str) -> list[MemberRecord]:
        models = self._session.scalars(
            select(MembershipModel)
            .join(OrganizationModel, MembershipModel.organization_id == OrganizationModel.id)
            .where(OrganizationModel.public_id == organization_public_id)
            .order_by(MembershipModel.name, MembershipModel.public_id)
        )
        return [MemberRecord.model_validate(model) for model in models]

    def list_invitations(self, organization_public_id: str) -> list[InvitationRecord]:
        rows = self._session.execute(
            select(InvitationModel, MembershipModel.public_id)
            .join(OrganizationModel, InvitationModel.organization_id == OrganizationModel.id)
            .join(MembershipModel, InvitationModel.invited_by_id == MembershipModel.id)
            .where(OrganizationModel.public_id == organization_public_id)
            .order_by(InvitationModel.created_at.desc())
        )
        return [self._invitation_record(model, inviter_id) for model, inviter_id in rows]

    def create_invitation(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        email: EmailStr,
        role: MemberRole,
        correlation_id: str,
    ) -> InvitationRecord:
        organization = self._organization_model(organization_public_id)
        if organization is None:
            raise ActorMembershipNotFound("The actor organization was not found.")
        inviter = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.status == "active",
                or_(MembershipModel.public_id == actor_id, MembershipModel.subject_id == actor_id),
            )
        )
        if inviter is None:
            raise ActorMembershipNotFound("The actor is not an active organization member.")
        normalized_email = str(email).lower()
        existing_member = self._session.scalar(
            select(MembershipModel.id).where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.email == normalized_email,
            )
        )
        if existing_member is not None:
            raise InvitationConflict(
                "This email address already belongs to a workspace member."
            )
        existing = self._session.scalar(
            select(InvitationModel).where(
                InvitationModel.organization_id == organization.id,
                InvitationModel.email == normalized_email,
                InvitationModel.status == InvitationStatus.PENDING.value,
            )
        )
        if existing is not None:
            raise InvitationConflict("A pending invitation already exists for this email address.")

        invitation = InvitationModel(
            public_id=f"INV-{uuid4().hex[:8].upper()}",
            organization_id=organization.id,
            email=normalized_email,
            role=role.value,
            status=InvitationStatus.PENDING.value,
            invited_by_id=inviter.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        self._session.add(invitation)
        self._session.flush()
        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="membership.invited",
                actor_type="member",
                actor_id=actor_id,
                subject_type="invitation",
                subject_id=invitation.public_id,
                summary="Member invitation created.",
                data={"role": role.value},
                correlation_id=correlation_id,
            )
        )
        return self._invitation_record(invitation, inviter.public_id)

    def attach_invitation_delivery(
        self,
        *,
        organization_public_id: str,
        invitation_public_id: str,
        provider_invitation_id: str,
    ) -> InvitationRecord:
        row = self._session.execute(
            select(InvitationModel, MembershipModel.public_id)
            .join(
                OrganizationModel,
                InvitationModel.organization_id == OrganizationModel.id,
            )
            .join(
                MembershipModel,
                InvitationModel.invited_by_id == MembershipModel.id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                InvitationModel.public_id == invitation_public_id,
                InvitationModel.status == InvitationStatus.PENDING.value,
            )
            .with_for_update()
        ).one_or_none()
        if row is None:
            raise InvitationNotFound("The invitation was not found.")
        invitation, inviter_public_id = row
        invitation.provider_invitation_id = provider_invitation_id
        self._session.flush()
        return self._invitation_record(invitation, inviter_public_id)

    def accept_invitation(
        self,
        *,
        identity: InvitedIdentity,
        correlation_id: str,
    ) -> ActorContext:
        existing_actor = self._accepted_actor(identity)
        if existing_actor is not None:
            return existing_actor
        base_conditions = [
            InvitationModel.email == str(identity.email).lower(),
            InvitationModel.status == InvitationStatus.PENDING.value,
        ]
        conditions = list(base_conditions)
        has_metadata_hint = (
            identity.invitation_id is not None
            or identity.organization_id is not None
        )
        if identity.invitation_id is not None:
            conditions.append(InvitationModel.public_id == identity.invitation_id)
        if identity.organization_id is not None:
            conditions.append(OrganizationModel.public_id == identity.organization_id)

        rows = self._session.execute(
            select(InvitationModel, OrganizationModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == InvitationModel.organization_id,
            )
            .where(*conditions)
            .order_by(InvitationModel.created_at.desc())
            .limit(2)
            .with_for_update()
        ).all()
        if len(rows) != 1 and has_metadata_hint:
            rows = self._session.execute(
                select(InvitationModel, OrganizationModel)
                .join(
                    OrganizationModel,
                    OrganizationModel.id == InvitationModel.organization_id,
                )
                .where(*base_conditions)
                .order_by(InvitationModel.created_at.desc())
                .limit(2)
                .with_for_update()
            ).all()
        if len(rows) != 1:
            existing_actor = self._accepted_actor(identity)
            if existing_actor is not None:
                return existing_actor
            raise ActorMembershipNotFound(
                "The verified account does not match one pending workspace invitation."
            )

        invitation, organization = rows[0]
        now = datetime.now(UTC)
        if invitation.expires_at <= now:
            raise ActorMembershipNotFound("The workspace invitation has expired.")

        existing = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization.id,
                or_(
                    MembershipModel.subject_id == identity.subject_id,
                    MembershipModel.email == str(identity.email).lower(),
                ),
            )
        )
        if existing is not None:
            raise ActorMembershipNotFound(
                "The account identity conflicts with an existing workspace member."
            )

        member = MembershipModel(
            public_id=f"USR-{uuid4().hex[:12].upper()}",
            organization_id=organization.id,
            subject_id=identity.subject_id,
            name=identity.name,
            email=str(identity.email).lower(),
            role=invitation.role,
            status=MemberStatus.ACTIVE.value,
            version=1,
            last_active_at=now,
        )
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = now
        invitation.version += 1
        invitation.updated_at = now
        self._session.add(member)
        self._session.flush()
        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="membership.invitation_accepted",
                actor_type="member",
                actor_id=member.public_id,
                subject_type="invitation",
                subject_id=invitation.public_id,
                summary="Member invitation accepted.",
                data={"role": invitation.role, "member_id": member.public_id},
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return self.resolve_actor_by_subject(identity.subject_id)

    def _accepted_actor(self, identity: InvitedIdentity) -> ActorContext | None:
        try:
            actor = self.resolve_actor_by_subject(identity.subject_id)
        except ActorMembershipNotFound:
            return None
        if (
            identity.organization_id is not None
            and actor.organization_id != identity.organization_id
        ):
            raise ActorMembershipNotFound(
                "The active workspace does not match the invitation."
            )
        return actor

    def update_member(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        member_public_id: str,
        expected_version: int,
        role: MemberRole | None,
        status: MemberStatus | None,
        correlation_id: str,
    ) -> MemberRecord:
        organization = self._session.scalar(
            select(OrganizationModel)
            .where(OrganizationModel.public_id == organization_public_id)
            .with_for_update()
        )
        if organization is None:
            raise ActorMembershipNotFound("The actor organization was not found.")
        actor = self._active_member(organization.id, actor_id)
        target = self._session.scalar(
            select(MembershipModel)
            .where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.public_id == member_public_id,
            )
            .with_for_update()
        )
        if target is None:
            raise MemberNotFound("The member was not found.")
        if target.version != expected_version:
            raise MemberVersionConflict(
                expected_version=expected_version,
                current_version=target.version,
            )
        next_role = role.value if role is not None else target.role
        next_status = status.value if status is not None else target.status
        if target.id == actor.id and (next_role != target.role or next_status != target.status):
            raise MemberConflict(
                "You cannot change your own role or deactivate your own membership."
            )
        if target.status == MemberStatus.INVITED.value:
            raise MemberConflict(
                "Invited people must accept or have their invitation revoked first."
            )
        if next_status == MemberStatus.INVITED.value:
            raise MemberConflict("An existing membership cannot be changed to invited.")
        if (
            target.role == MemberRole.ADMINISTRATOR.value
            and target.status == MemberStatus.ACTIVE.value
            and (
                next_role != MemberRole.ADMINISTRATOR.value
                or next_status != MemberStatus.ACTIVE.value
            )
        ):
            active_administrators = int(
                self._session.scalar(
                    select(func.count(MembershipModel.id)).where(
                        MembershipModel.organization_id == organization.id,
                        MembershipModel.role == MemberRole.ADMINISTRATOR.value,
                        MembershipModel.status == MemberStatus.ACTIVE.value,
                        MembershipModel.id != target.id,
                    )
                )
                or 0
            )
            if active_administrators == 0:
                raise MemberConflict(
                    "At least one active administrator must remain in the organization."
                )

        previous_role = target.role
        previous_status = target.status
        if next_role == previous_role and next_status == previous_status:
            return MemberRecord.model_validate(target)
        target.role = next_role
        target.status = next_status
        target.version += 1
        target.updated_at = datetime.now(UTC)
        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="membership.changed",
                actor_type="member",
                actor_id=actor.public_id,
                subject_type="member",
                subject_id=target.public_id,
                summary="Member authority changed.",
                data={
                    "previous_role": previous_role,
                    "role": target.role,
                    "previous_status": previous_status,
                    "status": target.status,
                    "version": target.version,
                },
                correlation_id=correlation_id,
            )
        )
        self._session.flush()
        return MemberRecord.model_validate(target)

    def revoke_invitation(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        invitation_public_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> InvitationRecord:
        organization = self._session.scalar(
            select(OrganizationModel)
            .where(OrganizationModel.public_id == organization_public_id)
            .with_for_update()
        )
        if organization is None:
            raise ActorMembershipNotFound("The actor organization was not found.")
        actor = self._active_member(organization.id, actor_id)
        invitation = self._session.scalar(
            select(InvitationModel)
            .where(
                InvitationModel.organization_id == organization.id,
                InvitationModel.public_id == invitation_public_id,
            )
            .with_for_update()
        )
        if invitation is None:
            raise InvitationNotFound("The invitation was not found.")
        if invitation.version != expected_version:
            raise InvitationVersionConflict(
                expected_version=expected_version,
                current_version=invitation.version,
            )
        if invitation.status != InvitationStatus.PENDING.value:
            raise InvitationConflict("Only a pending invitation can be revoked.")
        invitation.status = InvitationStatus.REVOKED.value
        invitation.version += 1
        invitation.updated_at = datetime.now(UTC)
        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="membership.invitation_revoked",
                actor_type="member",
                actor_id=actor.public_id,
                subject_type="invitation",
                subject_id=invitation.public_id,
                summary="Member invitation revoked.",
                data={"version": invitation.version},
                correlation_id=correlation_id,
            )
        )
        self._session.flush()
        inviter_public_id = self._session.scalar(
            select(MembershipModel.public_id).where(MembershipModel.id == invitation.invited_by_id)
        )
        if inviter_public_id is None:
            raise InvitationConflict("The original invitation owner is unavailable.")
        return self._invitation_record(invitation, inviter_public_id)

    def _active_member(self, organization_id: UUID, actor_id: str) -> MembershipModel:
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.status == MemberStatus.ACTIVE.value,
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound("The actor is not an active organization member.")
        return member

    @staticmethod
    def _invitation_record(model: InvitationModel, invited_by: str) -> InvitationRecord:
        return InvitationRecord(
            id=model.id,
            public_id=model.public_id,
            organization_id=model.organization_id,
            email=model.email,
            role=MemberRole(model.role),
            status=InvitationStatus(model.status),
            version=model.version,
            invited_by=invited_by,
            provider_invitation_id=model.provider_invitation_id,
            expires_at=model.expires_at,
            accepted_at=model.accepted_at,
        )
