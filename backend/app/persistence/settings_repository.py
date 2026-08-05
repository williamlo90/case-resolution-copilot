from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.identity import ActorMembershipNotFound
from app.domain.settings import (
    ApprovalSettingsValues,
    GeneralSettingsValues,
    OrganizationSettingsRecord,
    RetentionSettingsValues,
    SettingsConflict,
    SettingsSection,
    SettingsUpdateReceipt,
    SettingsValues,
    SettingsVersionConflict,
    default_settings,
    parse_settings_values,
)
from app.persistence.models import (
    AuditEventModel,
    MembershipModel,
    OrganizationModel,
    OrganizationSettingModel,
)


class OrganizationSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        organization_public_id: str,
        section: SettingsSection,
    ) -> OrganizationSettingsRecord | None:
        organization = self._organization(organization_public_id)
        if organization is None:
            return None
        model = self._session.scalar(
            select(OrganizationSettingModel).where(
                OrganizationSettingModel.organization_id == organization.id,
                OrganizationSettingModel.section == section.value,
            )
        )
        return self._record(organization=organization, section=section, model=model)

    def approval_values(
        self,
        *,
        organization_public_id: str,
    ) -> tuple[ApprovalSettingsValues, int]:
        record = self.get(
            organization_public_id=organization_public_id,
            section=SettingsSection.APPROVALS,
        )
        if record is None:
            raise SettingsConflict("The organization settings are unavailable.")
        values = record.configuration
        if not isinstance(values, ApprovalSettingsValues):
            raise SettingsConflict("The approval settings are invalid.")
        return values, record.version

    def retention_values(
        self,
        *,
        organization_public_id: str,
    ) -> tuple[RetentionSettingsValues, int]:
        record = self.get(
            organization_public_id=organization_public_id,
            section=SettingsSection.RETENTION,
        )
        if record is None:
            raise SettingsConflict("The organization settings are unavailable.")
        values = record.configuration
        if not isinstance(values, RetentionSettingsValues):
            raise SettingsConflict("The retention settings are invalid.")
        return values, record.version

    def update(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        section: SettingsSection,
        expected_version: int,
        configuration: SettingsValues,
        correlation_id: str,
    ) -> SettingsUpdateReceipt:
        organization = self._session.scalar(
            select(OrganizationModel)
            .where(OrganizationModel.public_id == organization_public_id)
            .with_for_update()
        )
        if organization is None:
            raise SettingsConflict("The organization settings are unavailable.")
        member = self._active_member(
            organization_id=organization.id,
            actor_id=actor_id,
        )
        model = self._session.scalar(
            select(OrganizationSettingModel)
            .where(
                OrganizationSettingModel.organization_id == organization.id,
                OrganizationSettingModel.section == section.value,
            )
            .with_for_update()
        )
        current_version = model.version if model is not None else 1
        if expected_version != current_version:
            raise SettingsVersionConflict(
                expected_version=expected_version,
                current_version=current_version,
            )

        validated = parse_settings_values(
            section,
            configuration.model_dump(mode="json"),
        )
        now = datetime.now(UTC)
        next_version = current_version + 1
        if model is None:
            model = OrganizationSettingModel(
                public_id=_settings_public_id(organization.public_id, section),
                organization_id=organization.id,
                section=section.value,
                configuration=validated.model_dump(mode="json"),
                version=next_version,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        else:
            model.configuration = validated.model_dump(mode="json")
            model.version = next_version
            model.updated_at = now

        if section is SettingsSection.GENERAL:
            if not isinstance(validated, GeneralSettingsValues):
                raise SettingsConflict("The general settings are invalid.")
            organization.name = validated.organization_name
            organization.version += 1
            organization.updated_at = now

        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="organization.settings_changed",
                actor_type="member",
                actor_id=member.public_id,
                subject_type="settings",
                subject_id=model.public_id,
                summary=f"{section.value.title()} settings changed.",
                data={
                    "section": section.value,
                    "previous_version": current_version,
                    "version": next_version,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return SettingsUpdateReceipt(
            settings=self._record(
                organization=organization,
                section=section,
                model=model,
            ),
            changed_by_id=member.public_id,
            changed_by_name=member.name,
            changed_at=now,
            correlation_id=correlation_id,
        )

    def ensure_defaults(
        self,
        *,
        organization_public_id: str,
    ) -> list[OrganizationSettingsRecord]:
        organization = self._session.scalar(
            select(OrganizationModel)
            .where(OrganizationModel.public_id == organization_public_id)
            .with_for_update()
        )
        if organization is None:
            raise SettingsConflict("The organization settings are unavailable.")
        existing = {
            model.section: model
            for model in self._session.scalars(
                select(OrganizationSettingModel).where(
                    OrganizationSettingModel.organization_id == organization.id
                )
            )
        }
        now = datetime.now(UTC)
        for section in SettingsSection:
            if section.value in existing:
                continue
            model = OrganizationSettingModel(
                public_id=_settings_public_id(organization.public_id, section),
                organization_id=organization.id,
                section=section.value,
                configuration=default_settings(
                    section,
                    organization_name=organization.name,
                ).model_dump(mode="json"),
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
            existing[section.value] = model
        self._session.flush()
        return [
            self._record(
                organization=organization,
                section=section,
                model=existing[section.value],
            )
            for section in SettingsSection
        ]

    def _organization(self, public_id: str) -> OrganizationModel | None:
        return self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == public_id)
        )

    def _active_member(self, *, organization_id: UUID, actor_id: str) -> MembershipModel:
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required to change settings."
            )
        return member

    @staticmethod
    def _record(
        *,
        organization: OrganizationModel,
        section: SettingsSection,
        model: OrganizationSettingModel | None,
    ) -> OrganizationSettingsRecord:
        if model is None:
            return OrganizationSettingsRecord(
                id=None,
                public_id=_settings_public_id(organization.public_id, section),
                organization_id=organization.id,
                organization_public_id=organization.public_id,
                section=section,
                configuration=default_settings(
                    section,
                    organization_name=organization.name,
                ),
                version=1,
                created_at=organization.created_at,
                updated_at=organization.updated_at,
                persisted=False,
            )
        try:
            configuration = parse_settings_values(section, model.configuration)
        except ValidationError as exc:
            raise SettingsConflict(
                f"The stored {section.value} settings are invalid."
            ) from exc
        return OrganizationSettingsRecord(
            id=model.id,
            public_id=model.public_id,
            organization_id=model.organization_id,
            organization_public_id=organization.public_id,
            section=section,
            configuration=configuration,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
            persisted=True,
        )


def _settings_public_id(
    organization_public_id: str,
    section: SettingsSection,
) -> str:
    digest = sha256(f"{organization_public_id}:{section.value}".encode()).hexdigest()
    return f"SET-{digest[:12].upper()}"
