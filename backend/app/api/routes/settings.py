from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.settings import present_settings, present_settings_receipt
from app.api.schemas.settings import (
    SettingsDetailEnvelope,
    SettingsUpdateEnvelope,
    SettingsUpdateRequest,
    domain_settings_values,
)
from app.domain.identity import ActorContext, ActorMembershipNotFound, Permission
from app.domain.settings import (
    SettingsConflict,
    SettingsNotFound,
    SettingsSection,
    SettingsVersionConflict,
)
from app.persistence.database import Database
from app.persistence.settings_repository import OrganizationSettingsRepository
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Organization settings are not available.",
            status_code=503,
        )
    return database


def _translate(error: Exception) -> AppError:
    if isinstance(error, SettingsNotFound):
        return AppError(
            code="settings_not_found",
            message=str(error),
            status_code=404,
        )
    if isinstance(error, ActorMembershipNotFound):
        return AppError(
            code="active_membership_required",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, SettingsVersionConflict):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    return AppError(
        code="settings_conflict",
        message=str(error),
        status_code=409,
    )


@router.get("/{section}", response_model=SettingsDetailEnvelope)
def get_settings(
    section: SettingsSection,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> SettingsDetailEnvelope:
    authorize_actor(
        actor,
        Permission.SETTINGS_MANAGE,
        error_code="settings_manage_forbidden",
    )
    try:
        with _database(request).session() as session:
            record = SettingsService(
                OrganizationSettingsRepository(session)
            ).get(actor=actor, section=section)
    except (SettingsConflict, SettingsNotFound) as exc:
        raise _translate(exc) from exc
    return SettingsDetailEnvelope(data=present_settings(record))


@router.put("/{section}", response_model=SettingsUpdateEnvelope)
def update_settings(
    section: SettingsSection,
    command: SettingsUpdateRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> SettingsUpdateEnvelope:
    authorize_actor(
        actor,
        Permission.SETTINGS_MANAGE,
        error_code="settings_manage_forbidden",
    )
    if command.section != section.value:
        raise AppError(
            code="settings_section_mismatch",
            message="The settings section in the request does not match the URL.",
            status_code=422,
        )
    try:
        with _database(request).session() as session:
            receipt = SettingsService(
                OrganizationSettingsRepository(session)
            ).update(
                actor=actor,
                section=section,
                expected_version=command.expected_version,
                configuration=domain_settings_values(command),
                correlation_id=str(request.state.correlation_id),
            )
    except (
        ActorMembershipNotFound,
        SettingsConflict,
        SettingsNotFound,
        SettingsVersionConflict,
    ) as exc:
        raise _translate(exc) from exc
    return SettingsUpdateEnvelope(data=present_settings_receipt(receipt))
