from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.domain.policies import (
    CasePolicyEvidenceRecord,
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    IndexedPolicyClause,
    PolicyActorNotAssignable,
    PolicyConcurrencyConflict,
    PolicyDraftContent,
    PolicyEvidenceUsageRecord,
    PolicyNotFound,
    PolicyOwnerRecord,
    PolicyRecord,
    PolicyVersionBundle,
    PolicyVersionConcurrencyConflict,
    PolicyVersionStatus,
    PolicyWorkspaceRecord,
)
from app.persistence.models import (
    AuditEventModel,
    CaseModel,
    CasePolicyEvidenceModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    PolicyModel,
    utc_now,
)
from app.retrieval.policy_parser import (
    GOVERNED_CHUNKING_VERSION,
    GOVERNED_INDEX_VERSION,
)


class PolicyRepositoryBase:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_workspace(
        self, *, organization_public_id: str, policy_public_id: str
    ) -> PolicyWorkspaceRecord | None:
        owner = aliased(MembershipModel)
        row = self._session.execute(
            select(PolicyModel, owner)
            .join(OrganizationModel, OrganizationModel.id == PolicyModel.organization_id)
            .join(
                owner,
                and_(
                    owner.organization_id == PolicyModel.organization_id,
                    owner.id == PolicyModel.owner_id,
                ),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                PolicyModel.public_id == policy_public_id,
            )
        ).one_or_none()
        if row is None:
            return None
        policy, member = row
        version_models = list(
            self._session.scalars(
                select(GovernedPolicyVersionModel)
                .where(
                    GovernedPolicyVersionModel.organization_id == policy.organization_id,
                    GovernedPolicyVersionModel.policy_id == policy.id,
                )
                .order_by(GovernedPolicyVersionModel.version.desc())
            )
        )
        bundles = [self._version_bundle(policy, version) for version in version_models]
        return PolicyWorkspaceRecord(
            policy=PolicyRecord.model_validate(policy),
            owner=self._owner_record(member),
            versions=bundles,
        )

    def _add_version(
        self,
        *,
        policy: PolicyModel,
        version_number: int,
        actor_id: str,
        content: PolicyDraftContent,
        clauses: list[IndexedPolicyClause],
        legacy_policy_version_id: UUID | None,
    ) -> GovernedPolicyVersionModel:
        version_uuid = uuid4()
        version = GovernedPolicyVersionModel(
            id=version_uuid,
            public_id=_stable_public_id("POLV", policy.public_id, str(version_number)),
            organization_id=policy.organization_id,
            policy_id=policy.id,
            legacy_policy_version_id=legacy_policy_version_id,
            version=version_number,
            record_version=1,
            status=PolicyVersionStatus.DRAFT.value,
            immutable=False,
            source_text=content.source_text,
            content_hash=sha256(content.source_text.encode()).hexdigest(),
            decision_scope=content.applicability.decision_scope,
            case_categories=content.applicability.case_categories,
            products=content.applicability.products,
            regions=content.applicability.regions,
            channels=content.applicability.channels,
            customer_tiers=content.applicability.customer_tiers,
            effective_from=content.effective_from,
            effective_to=content.effective_to,
            created_by=actor_id,
        )
        clause_models = [
            GovernedPolicyClauseModel(
                public_id=_stable_public_id(
                    "POLC", policy.public_id, str(version_number), str(sequence)
                ),
                organization_id=policy.organization_id,
                policy_id=policy.id,
                policy_version_id=version_uuid,
                sequence=sequence,
                heading=indexed_clause.clause.heading,
                text=indexed_clause.clause.text,
                applies_when=indexed_clause.clause.applies_when,
                content_hash=sha256(indexed_clause.clause.text.encode()).hexdigest(),
                chunking_version=GOVERNED_CHUNKING_VERSION,
                embedding_version=indexed_clause.embedding_version,
                index_version=GOVERNED_INDEX_VERSION,
                embedding=indexed_clause.embedding,
            )
            for sequence, indexed_clause in enumerate(clauses, start=1)
        ]
        self._session.add(version)
        self._session.flush()
        self._session.add_all(clause_models)
        self._session.flush()
        return version

    def _version_bundle(
        self, policy: PolicyModel, version: GovernedPolicyVersionModel
    ) -> PolicyVersionBundle:
        clauses = self._clause_records(policy, version)
        evidence_rows = self._session.execute(
            select(CasePolicyEvidenceModel, CaseModel.public_id)
            .join(
                CaseModel,
                and_(
                    CaseModel.organization_id == CasePolicyEvidenceModel.organization_id,
                    CaseModel.id == CasePolicyEvidenceModel.case_id,
                ),
            )
            .where(
                CasePolicyEvidenceModel.organization_id == policy.organization_id,
                CasePolicyEvidenceModel.policy_version_id == version.id,
            )
        )
        return PolicyVersionBundle(
            version=GovernedPolicyVersionRecord.model_validate(version),
            clauses=clauses,
            evidence=[
                PolicyEvidenceUsageRecord(
                    evidence=CasePolicyEvidenceRecord.model_validate(model),
                    case_public_id=case_public_id,
                )
                for model, case_public_id in evidence_rows
            ],
        )

    def _clause_records(
        self, policy: PolicyModel, version: GovernedPolicyVersionModel
    ) -> list[GovernedPolicyClauseRecord]:
        models = self._session.scalars(
            select(GovernedPolicyClauseModel)
            .where(
                GovernedPolicyClauseModel.organization_id == policy.organization_id,
                GovernedPolicyClauseModel.policy_id == policy.id,
                GovernedPolicyClauseModel.policy_version_id == version.id,
            )
            .order_by(GovernedPolicyClauseModel.sequence)
        )
        return [GovernedPolicyClauseRecord.model_validate(model) for model in models]

    def _required_policy(self, organization_public_id: str, policy_public_id: str) -> PolicyModel:
        model = self._session.scalar(
            select(PolicyModel)
            .join(OrganizationModel, OrganizationModel.id == PolicyModel.organization_id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                PolicyModel.public_id == policy_public_id,
            )
        )
        if model is None:
            raise PolicyNotFound("The policy was not found.")
        return model

    def _required_version(
        self, policy: PolicyModel, version_number: int
    ) -> GovernedPolicyVersionModel:
        model = self._session.scalar(
            select(GovernedPolicyVersionModel).where(
                GovernedPolicyVersionModel.organization_id == policy.organization_id,
                GovernedPolicyVersionModel.policy_id == policy.id,
                GovernedPolicyVersionModel.version == version_number,
            )
        )
        if model is None:
            raise PolicyNotFound("The policy version was not found.")
        return model

    def _required_workspace(
        self, organization_public_id: str, policy_public_id: str
    ) -> PolicyWorkspaceRecord:
        workspace = self.get_workspace(
            organization_public_id=organization_public_id,
            policy_public_id=policy_public_id,
        )
        if workspace is None:
            raise PolicyNotFound("The policy was not found.")
        return workspace

    def _required_case(self, organization_public_id: str, case_public_id: str) -> CaseModel:
        model = self._session.scalar(
            select(CaseModel)
            .join(OrganizationModel, OrganizationModel.id == CaseModel.organization_id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        )
        if model is None:
            raise PolicyNotFound("The case was not found.")
        return model

    def _organization_id(self, public_id: str) -> UUID | None:
        return self._session.scalar(
            select(OrganizationModel.id).where(OrganizationModel.public_id == public_id)
        )

    def _required_member(self, organization_id: UUID, actor_id: str) -> MembershipModel:
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
            raise PolicyActorNotAssignable("The actor is not an active organization member.")
        return member

    def _update_policy(
        self,
        *,
        policy: PolicyModel,
        expected_version: int,
        values: dict[str, object],
    ) -> PolicyModel:
        updated = self._session.scalar(
            update(PolicyModel)
            .where(
                PolicyModel.id == policy.id,
                PolicyModel.organization_id == policy.organization_id,
                PolicyModel.version == expected_version,
            )
            .values(**values, version=PolicyModel.version + 1, updated_at=utc_now())
            .returning(PolicyModel)
        )
        if updated is None:
            current = self._session.scalar(
                select(PolicyModel.version).where(
                    PolicyModel.id == policy.id,
                    PolicyModel.organization_id == policy.organization_id,
                )
            )
            if current is None:
                raise PolicyNotFound("The policy was not found.")
            raise PolicyConcurrencyConflict(
                expected_version=expected_version,
                current_version=current,
            )
        return updated

    def _update_version(
        self,
        *,
        version: GovernedPolicyVersionModel,
        expected_version: int,
        values: dict[str, object],
    ) -> GovernedPolicyVersionModel:
        updated = self._session.scalar(
            update(GovernedPolicyVersionModel)
            .where(
                GovernedPolicyVersionModel.id == version.id,
                GovernedPolicyVersionModel.organization_id == version.organization_id,
                GovernedPolicyVersionModel.record_version == expected_version,
            )
            .values(
                **values,
                record_version=GovernedPolicyVersionModel.record_version + 1,
            )
            .returning(GovernedPolicyVersionModel)
        )
        if updated is None:
            current = self._session.scalar(
                select(GovernedPolicyVersionModel.record_version).where(
                    GovernedPolicyVersionModel.id == version.id,
                    GovernedPolicyVersionModel.organization_id == version.organization_id,
                )
            )
            if current is None:
                raise PolicyNotFound("The policy version was not found.")
            raise PolicyVersionConcurrencyConflict(
                expected_version=expected_version,
                current_version=current,
            )
        return updated

    def _audit(
        self,
        *,
        policy: PolicyModel,
        actor_id: str,
        actor_type: str,
        event_type: str,
        summary: str,
        data: dict[str, object],
        correlation_id: str,
    ) -> None:
        self._session.add(
            AuditEventModel(
                organization_id=policy.organization_id,
                task_id=None,
                run_id=None,
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                subject_type="policy",
                subject_id=policy.public_id,
                summary=summary,
                data=data,
                correlation_id=correlation_id,
            )
        )

    def _audit_case_evidence(
        self,
        *,
        case: CaseModel,
        actor_id: str,
        actor_type: str,
        fingerprints: list[str],
        correlation_id: str,
    ) -> None:
        self._session.add(
            AuditEventModel(
                organization_id=case.organization_id,
                task_id=None,
                run_id=None,
                event_type="case.policy_evidence_recorded",
                actor_type=actor_type,
                actor_id=actor_id,
                subject_type="case",
                subject_id=case.public_id,
                summary="Applicable policy evidence recorded.",
                data={"fingerprints": fingerprints},
                correlation_id=correlation_id,
            )
        )

    @staticmethod
    def _owner_record(model: MembershipModel) -> PolicyOwnerRecord:
        return PolicyOwnerRecord(id=model.id, public_id=model.public_id, name=model.name)


def _json_dimension_match(
    column: InstrumentedAttribute[list[str]],
    values: set[str],
) -> ColumnElement[bool]:
    normalized = sorted(values)
    return or_(
        column.contains(["all"]),
        *(column.contains([value]) for value in normalized),
    )


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"
