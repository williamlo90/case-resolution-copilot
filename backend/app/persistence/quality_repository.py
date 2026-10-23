import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.quality import (
    CaseQualityProjectionRecord,
    QualityCategory,
    QualityConflict,
    QualityDashboardRecord,
    QualityMetricRecord,
    QualityOperationalSummary,
    QualityProjectionSeed,
    QualityResult,
)
from app.persistence.models import (
    AuditEventModel,
    CaseActionModel,
    CaseModel,
    CaseQualityProjectionModel,
    CaseReviewModel,
    MembershipModel,
    OrganizationModel,
)


class QualityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def dashboard(
        self,
        *,
        organization_public_id: str,
        category: QualityCategory | None,
        limit: int,
    ) -> QualityDashboardRecord:
        organization = self._organization(organization_public_id)
        if organization is None:
            raise QualityConflict("The quality workspace was not found.")

        evidence_conditions = [
            CaseQualityProjectionModel.organization_id == organization.id
        ]
        if category is not None:
            evidence_conditions.append(
                CaseQualityProjectionModel.category == category.value
            )
        total = int(
            self._session.scalar(
                select(func.count(CaseQualityProjectionModel.id)).where(
                    *evidence_conditions
                )
            )
            or 0
        )
        models = list(
            self._session.scalars(
                select(CaseQualityProjectionModel)
                .where(*evidence_conditions)
                .order_by(
                    CaseQualityProjectionModel.evaluated_at.desc(),
                    CaseQualityProjectionModel.public_id.desc(),
                )
                .limit(limit)
            )
        )
        source_updated_at = self._session.scalar(
            select(func.max(CaseQualityProjectionModel.updated_at)).where(
                CaseQualityProjectionModel.organization_id == organization.id
            )
        )
        metrics = self._metrics(organization.id)
        operational = self._operational_summary(organization.id)
        return QualityDashboardRecord(
            metrics=metrics,
            operational=operational,
            evidence=[
                CaseQualityProjectionRecord.model_validate(model) for model in models
            ],
            available_categories=list(QualityCategory),
            generated_at=datetime.now(UTC),
            source_updated_at=source_updated_at,
            total=total,
        )

    def get_case(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> list[CaseQualityProjectionRecord] | None:
        organization = self._organization(organization_public_id)
        if organization is None:
            return None
        case = self._session.scalar(
            select(CaseModel).where(
                CaseModel.organization_id == organization.id,
                CaseModel.public_id == case_public_id,
            )
        )
        if case is None:
            return None
        models = self._session.scalars(
            select(CaseQualityProjectionModel)
            .where(
                CaseQualityProjectionModel.organization_id == organization.id,
                CaseQualityProjectionModel.case_id == case.id,
            )
            .order_by(
                CaseQualityProjectionModel.category,
                CaseQualityProjectionModel.evaluated_at.desc(),
            )
        )
        return [CaseQualityProjectionRecord.model_validate(model) for model in models]

    def upsert_projection(
        self,
        *,
        organization_public_id: str,
        seed: QualityProjectionSeed,
        correlation_id: str,
    ) -> CaseQualityProjectionRecord:
        organization = self._organization(organization_public_id)
        if organization is None:
            raise QualityConflict("The quality workspace was not found.")
        case = self._session.scalar(
            select(CaseModel).where(
                CaseModel.organization_id == organization.id,
                CaseModel.public_id == seed.case_public_id,
            )
        )
        evaluator = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.public_id == seed.evaluated_by_public_id,
                MembershipModel.status == "active",
            )
        )
        if case is None:
            raise QualityConflict("The evaluated case was not found.")
        if evaluator is None:
            raise QualityConflict("The quality evaluator is not an active member.")

        fingerprint = _projection_fingerprint(seed)
        model = self._session.scalar(
            select(CaseQualityProjectionModel)
            .where(
                CaseQualityProjectionModel.organization_id == organization.id,
                CaseQualityProjectionModel.case_id == case.id,
                CaseQualityProjectionModel.category == seed.category.value,
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        changed = False
        if model is None:
            model = CaseQualityProjectionModel(
                public_id=_stable_public_id(
                    "QLT",
                    organization.public_id,
                    case.public_id,
                    seed.category.value,
                ),
                organization_id=organization.id,
                case_id=case.id,
                case_public_id=case.public_id,
                category=seed.category.value,
                scenario=seed.scenario,
                expected_decision=seed.expected_decision,
                observed_decision=seed.observed_decision,
                policy_evidence=seed.policy_evidence,
                policy_evidence_present=seed.policy_evidence_present,
                customer_or_business_impact=seed.customer_or_business_impact,
                result=seed.result.value,
                evaluated_by_id=evaluator.id,
                evaluated_by_public_id=evaluator.public_id,
                evaluated_by_name=evaluator.name,
                source=seed.source.value,
                source_fingerprint=fingerprint,
                version=1,
                evaluated_at=seed.evaluated_at,
                updated_at=now,
            )
            self._session.add(model)
            changed = True
        elif model.source_fingerprint != fingerprint:
            model.scenario = seed.scenario
            model.expected_decision = seed.expected_decision
            model.observed_decision = seed.observed_decision
            model.policy_evidence = seed.policy_evidence
            model.policy_evidence_present = seed.policy_evidence_present
            model.customer_or_business_impact = seed.customer_or_business_impact
            model.result = seed.result.value
            model.evaluated_by_id = evaluator.id
            model.evaluated_by_public_id = evaluator.public_id
            model.evaluated_by_name = evaluator.name
            model.source = seed.source.value
            model.source_fingerprint = fingerprint
            model.version += 1
            model.evaluated_at = seed.evaluated_at
            model.updated_at = now
            changed = True

        self._session.flush()
        if changed:
            self._session.add(
                AuditEventModel(
                    organization_id=organization.id,
                    task_id=None,
                    run_id=None,
                    event_type="case.quality_projected",
                    actor_type="member",
                    actor_id=evaluator.public_id,
                    subject_type="case",
                    subject_id=case.public_id,
                    summary="Case quality evidence was projected.",
                    data={
                        "projection_id": model.public_id,
                        "category": model.category,
                        "result": model.result,
                        "version": model.version,
                    },
                    correlation_id=correlation_id,
                    occurred_at=seed.evaluated_at,
                )
            )
            self._session.flush()
        return CaseQualityProjectionRecord.model_validate(model)

    def _metrics(self, organization_id: UUID) -> list[QualityMetricRecord]:
        decision_total, decision_passed, decision_ids = self._projection_counts(
            organization_id=organization_id,
            category=QualityCategory.DECISION_QUALITY,
        )
        safety_total, safety_passed, safety_ids = self._projection_counts(
            organization_id=organization_id,
            category=QualityCategory.SAFETY,
        )
        policy_total = int(
            self._session.scalar(
                select(func.count(CaseQualityProjectionModel.id)).where(
                    CaseQualityProjectionModel.organization_id == organization_id
                )
            )
            or 0
        )
        policy_present = int(
            self._session.scalar(
                select(func.count(CaseQualityProjectionModel.id)).where(
                    CaseQualityProjectionModel.organization_id == organization_id,
                    CaseQualityProjectionModel.policy_evidence_present.is_(True),
                )
            )
            or 0
        )
        policy_ids = list(
            self._session.scalars(
                select(CaseQualityProjectionModel.case_public_id)
                .where(
                    CaseQualityProjectionModel.organization_id == organization_id,
                    CaseQualityProjectionModel.policy_evidence_present.is_(False),
                )
                .distinct()
                .limit(200)
            )
        )
        outcome_ids = list(
            self._session.scalars(
                select(CaseModel.public_id)
                .join(
                    CaseActionModel,
                    CaseActionModel.case_id == CaseModel.id,
                )
                .where(
                    CaseActionModel.organization_id == organization_id,
                    CaseActionModel.status.in_(
                        ["outcome_unknown", "recovery_required"]
                    ),
                )
                .distinct()
                .limit(200)
            )
        )
        outcome_count = int(
            self._session.scalar(
                select(func.count(CaseActionModel.id)).where(
                    CaseActionModel.organization_id == organization_id,
                    CaseActionModel.status.in_(
                        ["outcome_unknown", "recovery_required"]
                    ),
                )
            )
            or 0
        )
        return [
            _percentage_metric(
                key="expected_decisions",
                label="Expected decisions",
                numerator=decision_passed,
                denominator=decision_total,
                filtered_case_ids=decision_ids,
            ),
            _percentage_metric(
                key="unsafe_actions_blocked",
                label="Unsafe actions blocked",
                numerator=safety_passed,
                denominator=safety_total,
                filtered_case_ids=safety_ids,
            ),
            _percentage_metric(
                key="policy_evidence_present",
                label="Policy evidence present",
                numerator=policy_present,
                denominator=policy_total,
                filtered_case_ids=policy_ids,
            ),
            QualityMetricRecord(
                key="outcome_checks_pending",
                label="Outcome checks pending",
                value=outcome_count,
                unit="count",
                numerator=None,
                denominator=None,
                status="healthy" if outcome_count == 0 else "needs_attention",
                filtered_case_ids=outcome_ids,
            ),
        ]

    def _projection_counts(
        self,
        *,
        organization_id: UUID,
        category: QualityCategory,
    ) -> tuple[int, int, list[str]]:
        total = int(
            self._session.scalar(
                select(func.count(CaseQualityProjectionModel.id)).where(
                    CaseQualityProjectionModel.organization_id == organization_id,
                    CaseQualityProjectionModel.category == category.value,
                )
            )
            or 0
        )
        passed = int(
            self._session.scalar(
                select(func.count(CaseQualityProjectionModel.id)).where(
                    CaseQualityProjectionModel.organization_id == organization_id,
                    CaseQualityProjectionModel.category == category.value,
                    CaseQualityProjectionModel.result == QualityResult.PASSED.value,
                )
            )
            or 0
        )
        ids = list(
            self._session.scalars(
                select(CaseQualityProjectionModel.case_public_id)
                .where(
                    CaseQualityProjectionModel.organization_id == organization_id,
                    CaseQualityProjectionModel.category == category.value,
                    CaseQualityProjectionModel.result
                    == QualityResult.NEEDS_ATTENTION.value,
                )
                .distinct()
                .limit(200)
            )
        )
        return total, passed, ids

    def _operational_summary(
        self,
        organization_id: UUID,
    ) -> QualityOperationalSummary:
        open_cases = int(
            self._session.scalar(
                select(func.count(CaseModel.id)).where(
                    CaseModel.organization_id == organization_id,
                    CaseModel.status != "completed",
                )
            )
            or 0
        )
        waiting_reviews = int(
            self._session.scalar(
                select(func.count(CaseReviewModel.id)).where(
                    CaseReviewModel.organization_id == organization_id,
                    CaseReviewModel.status.in_(["pending", "reserved"]),
                )
            )
            or 0
        )
        action_count_rows = self._session.execute(
            select(
                CaseActionModel.status,
                func.count(CaseActionModel.id),
            )
            .where(CaseActionModel.organization_id == organization_id)
            .group_by(CaseActionModel.status)
        ).all()
        action_counts: dict[str, int] = {
            status: int(count) for status, count in action_count_rows
        }
        return QualityOperationalSummary(
            open_cases=open_cases,
            cases_waiting_for_review=waiting_reviews,
            actions_completed=int(action_counts.get("completed", 0)),
            actions_failed_safe=int(action_counts.get("failed_safe", 0)),
            actions_outcome_unknown=int(action_counts.get("outcome_unknown", 0))
            + int(action_counts.get("recovery_required", 0)),
            reopened_cases=None,
        )

    def _organization(self, public_id: str) -> OrganizationModel | None:
        return self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == public_id)
        )


def _percentage_metric(
    *,
    key: str,
    label: str,
    numerator: int,
    denominator: int,
    filtered_case_ids: list[str],
) -> QualityMetricRecord:
    if denominator == 0:
        return QualityMetricRecord(
            key=key,
            label=label,
            value=0,
            unit="percent",
            numerator=0,
            denominator=0,
            status="no_data",
            filtered_case_ids=[],
        )
    value = round((numerator / denominator) * 100, 1)
    return QualityMetricRecord(
        key=key,
        label=label,
        value=value,
        unit="percent",
        numerator=numerator,
        denominator=denominator,
        status="healthy" if numerator == denominator else "needs_attention",
        filtered_case_ids=filtered_case_ids,
    )


def _projection_fingerprint(seed: QualityProjectionSeed) -> str:
    return sha256(
        json.dumps(
            seed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"
