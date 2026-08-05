import base64
import binascii
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.domain.identity import ActorContext, Permission
from app.domain.policies import (
    GovernedPolicyVersionRecord,
    IndexedPolicyClause,
    InvalidPolicyTransition,
    ParsedPolicyClause,
    PolicyApplicability,
    PolicyCandidateRecord,
    PolicyCreate,
    PolicyDraftContent,
    PolicyLifecycleStatus,
    PolicyListPageRecord,
    PolicyNotFound,
    PolicySourceKind,
    PolicySourceParseError,
    PolicyVersionBundle,
    PolicyVersionStatus,
    PolicyWorkspaceRecord,
)
from app.retrieval.embeddings import (
    DEFAULT_EMBEDDING_PROVIDER,
    EmbeddingProvider,
)
from app.retrieval.policy_parser import parse_policy_source
from app.security.authorization import require_permission


class InvalidPolicyCursor(ValueError):
    pass


class PolicyStore(Protocol):
    def list_policies(
        self,
        *,
        organization_public_id: str,
        status: PolicyLifecycleStatus | None,
        query: str | None,
        offset: int,
        limit: int,
    ) -> PolicyListPageRecord: ...

    def get_workspace(
        self, *, organization_public_id: str, policy_public_id: str
    ) -> PolicyWorkspaceRecord | None: ...

    def create_policy(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        actor_type: str,
        command: PolicyCreate,
        clauses: list[IndexedPolicyClause],
        source_error: str | None,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def create_draft(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        content: PolicyDraftContent,
        clauses: list[IndexedPolicyClause],
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def retry_source(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        content: PolicyDraftContent,
        clauses: list[IndexedPolicyClause],
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def submit_review(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def mark_conflicting(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        conflicting_policy_ids: list[str],
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def activate_version(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        target: PolicyVersionStatus,
        effective_from: datetime,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def retire_version(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord: ...

    def list_candidates(self, *, organization_public_id: str) -> list[PolicyCandidateRecord]: ...


class PolicyService:
    def __init__(
        self,
        store: PolicyStore,
        embedding_provider: EmbeddingProvider = DEFAULT_EMBEDDING_PROVIDER,
    ) -> None:
        self._store = store
        self._embedding_provider = embedding_provider

    def list_policies(
        self,
        *,
        actor: ActorContext,
        status: PolicyLifecycleStatus | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> PolicyListPageRecord:
        require_permission(actor, Permission.POLICY_READ)
        return self._store.list_policies(
            organization_public_id=actor.organization_id,
            status=status,
            query=query,
            offset=decode_policy_cursor(cursor, status=status, query=query),
            limit=limit,
        )

    def get_policy(self, *, actor: ActorContext, policy_id: str) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_READ)
        workspace = self._store.get_workspace(
            organization_public_id=actor.organization_id,
            policy_public_id=policy_id,
        )
        if workspace is None:
            raise PolicyNotFound("The policy was not found.")
        return workspace

    def create_policy(
        self,
        *,
        actor: ActorContext,
        title: str,
        description: str,
        source_kind: PolicySourceKind,
        source_name: str,
        source_text: str | None,
        applicability: PolicyApplicability | None,
        effective_from: datetime | None,
        effective_to: datetime | None,
        public_id: str | None,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_MANAGE)
        content, parsed_clauses, source_error = self._prepare_source(
            source_text=source_text,
            applicability=applicability,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        clauses = self._index_clauses(parsed_clauses)
        command = PolicyCreate(
            public_id=public_id or f"POL-{uuid4().hex[:8].upper()}",
            title=title,
            description=description,
            source_kind=source_kind,
            source_name=source_name,
            content=content,
        )
        return self._store.create_policy(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            command=command,
            clauses=clauses,
            source_error=source_error,
            correlation_id=correlation_id,
        )

    def create_draft(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        expected_policy_version: int,
        content: PolicyDraftContent,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_MANAGE)
        clauses = self._index_clauses(
            parse_policy_source(content.source_text, content.applicability)
        )
        workspace = self.get_policy(actor=actor, policy_id=policy_id)
        if workspace.policy.status in {
            PolicyLifecycleStatus.DRAFT,
            PolicyLifecycleStatus.IN_REVIEW,
            PolicyLifecycleStatus.PARSING_FAILED,
        }:
            raise InvalidPolicyTransition(
                "Finish or recover the current policy version before creating another draft."
            )
        return self._store.create_draft(
            organization_public_id=actor.organization_id,
            policy_public_id=policy_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_policy_version=expected_policy_version,
            content=content,
            clauses=clauses,
            correlation_id=correlation_id,
        )

    def retry_source(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        expected_policy_version: int,
        content: PolicyDraftContent,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_MANAGE)
        clauses = self._index_clauses(
            parse_policy_source(content.source_text, content.applicability)
        )
        workspace = self.get_policy(actor=actor, policy_id=policy_id)
        if (
            workspace.policy.status is not PolicyLifecycleStatus.PARSING_FAILED
            or workspace.policy.current_version != 0
        ):
            raise InvalidPolicyTransition("Only a failed source can be retried.")
        return self._store.retry_source(
            organization_public_id=actor.organization_id,
            policy_public_id=policy_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_policy_version=expected_policy_version,
            content=content,
            clauses=clauses,
            correlation_id=correlation_id,
        )

    def submit_review(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        version_number: int,
        expected_policy_version: int,
        expected_version: int,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_MANAGE)
        workspace = self.get_policy(actor=actor, policy_id=policy_id)
        version = _required_current_version(workspace, version_number)
        if version.version.status is not PolicyVersionStatus.DRAFT:
            raise InvalidPolicyTransition("Only a draft policy version can enter review.")
        return self._store.submit_review(
            organization_public_id=actor.organization_id,
            policy_public_id=policy_id,
            version_number=version_number,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_policy_version=expected_policy_version,
            expected_version=expected_version,
            correlation_id=correlation_id,
        )

    def publish(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        version_number: int,
        expected_policy_version: int,
        expected_version: int,
        effective_from: datetime | None,
        correlation_id: str,
        now: datetime | None = None,
    ) -> PolicyWorkspaceRecord:
        current_time = now or datetime.now(UTC)
        return self._activate(
            actor=actor,
            policy_id=policy_id,
            version_number=version_number,
            expected_policy_version=expected_policy_version,
            expected_version=expected_version,
            requested_effective_from=effective_from,
            target=PolicyVersionStatus.PUBLISHED,
            current_time=current_time,
            correlation_id=correlation_id,
        )

    def schedule(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        version_number: int,
        expected_policy_version: int,
        expected_version: int,
        effective_from: datetime,
        correlation_id: str,
        now: datetime | None = None,
    ) -> PolicyWorkspaceRecord:
        current_time = now or datetime.now(UTC)
        return self._activate(
            actor=actor,
            policy_id=policy_id,
            version_number=version_number,
            expected_policy_version=expected_policy_version,
            expected_version=expected_version,
            requested_effective_from=effective_from,
            target=PolicyVersionStatus.SCHEDULED,
            current_time=current_time,
            correlation_id=correlation_id,
        )

    def retire(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        version_number: int,
        expected_policy_version: int,
        expected_version: int,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_MANAGE)
        workspace = self.get_policy(actor=actor, policy_id=policy_id)
        version = _required_current_version(workspace, version_number)
        if version.version.status not in {
            PolicyVersionStatus.PUBLISHED,
            PolicyVersionStatus.SCHEDULED,
        }:
            raise InvalidPolicyTransition("Only a published or scheduled policy can be retired.")
        return self._store.retire_version(
            organization_public_id=actor.organization_id,
            policy_public_id=policy_id,
            version_number=version_number,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_policy_version=expected_policy_version,
            expected_version=expected_version,
            correlation_id=correlation_id,
        )

    def _activate(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        version_number: int,
        expected_policy_version: int,
        expected_version: int,
        requested_effective_from: datetime | None,
        target: PolicyVersionStatus,
        current_time: datetime,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        require_permission(actor, Permission.POLICY_MANAGE)
        workspace = self.get_policy(actor=actor, policy_id=policy_id)
        bundle = _required_current_version(workspace, version_number)
        version = bundle.version
        if version.status is not PolicyVersionStatus.IN_REVIEW:
            raise InvalidPolicyTransition("Only an in-review policy version can be activated.")
        effective_from = requested_effective_from or version.effective_from or current_time
        if target is PolicyVersionStatus.PUBLISHED and effective_from > current_time:
            raise InvalidPolicyTransition("Use schedule for a future effective date.")
        if target is PolicyVersionStatus.SCHEDULED and effective_from <= current_time:
            raise InvalidPolicyTransition("A scheduled policy needs a future effective date.")
        if version.effective_to is not None and version.effective_to <= effective_from:
            raise InvalidPolicyTransition("The effective date is outside the policy window.")

        conflicts = _find_conflicts(
            version=version,
            policy_id=workspace.policy.public_id,
            effective_from=effective_from,
            candidates=self._store.list_candidates(organization_public_id=actor.organization_id),
        )
        if conflicts:
            return self._store.mark_conflicting(
                organization_public_id=actor.organization_id,
                policy_public_id=policy_id,
                version_number=version_number,
                actor_id=actor.actor_id,
                actor_type=actor.kind.value,
                expected_policy_version=expected_policy_version,
                expected_version=expected_version,
                conflicting_policy_ids=conflicts,
                correlation_id=correlation_id,
            )
        return self._store.activate_version(
            organization_public_id=actor.organization_id,
            policy_public_id=policy_id,
            version_number=version_number,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_policy_version=expected_policy_version,
            expected_version=expected_version,
            target=target,
            effective_from=effective_from,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _prepare_source(
        *,
        source_text: str | None,
        applicability: PolicyApplicability | None,
        effective_from: datetime | None,
        effective_to: datetime | None,
    ) -> tuple[PolicyDraftContent | None, list[ParsedPolicyClause], str | None]:
        if source_text is None:
            return None, [], "Source text is not available."
        if applicability is None:
            return None, [], "Policy applicability is not available."
        try:
            content = PolicyDraftContent(
                source_text=source_text,
                applicability=applicability,
                effective_from=effective_from,
                effective_to=effective_to,
            )
            return content, parse_policy_source(source_text, applicability), None
        except (PolicySourceParseError, ValueError) as exc:
            return None, [], str(exc)

    def _index_clauses(
        self,
        clauses: list[ParsedPolicyClause],
    ) -> list[IndexedPolicyClause]:
        return [
            IndexedPolicyClause(
                clause=clause,
                embedding_version=self._embedding_provider.version,
                embedding=self._embedding_provider.embed(clause.text),
            )
            for clause in clauses
        ]


def encode_policy_cursor(
    offset: int | None,
    *,
    status: PolicyLifecycleStatus | None,
    query: str | None,
) -> str | None:
    if offset is None:
        return None
    payload = {
        "offset": offset,
        "status": status.value if status is not None else None,
        "query": query.strip() if query is not None else None,
    }
    return (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        .decode()
        .rstrip("=")
    )


def decode_policy_cursor(
    cursor: str | None,
    *,
    status: PolicyLifecycleStatus | None,
    query: str | None,
) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(payload, dict) or set(payload) != {"offset", "status", "query"}:
            raise ValueError("Unexpected cursor fields.")
        offset = payload["offset"]
        if type(offset) is not int or offset < 0:
            raise ValueError("Cursor offset is invalid.")
        expected = {
            "status": status.value if status is not None else None,
            "query": query.strip() if query is not None else None,
        }
        if any(payload[key] != value for key, value in expected.items()):
            raise ValueError("Cursor filters do not match the request.")
        return offset
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise InvalidPolicyCursor("The policy cursor is invalid.") from exc


def _required_current_version(
    workspace: PolicyWorkspaceRecord, version_number: int
) -> PolicyVersionBundle:
    if workspace.policy.current_version != version_number:
        raise InvalidPolicyTransition("Only the current policy version can use this command.")
    for bundle in workspace.versions:
        if bundle.version.version == version_number:
            return bundle
    raise PolicyNotFound("The policy version was not found.")


def _find_conflicts(
    *,
    version: GovernedPolicyVersionRecord,
    policy_id: str,
    effective_from: datetime,
    candidates: Sequence[PolicyCandidateRecord],
) -> list[str]:
    conflicts = []
    for candidate in candidates:
        if candidate.policy.public_id == policy_id:
            continue
        other = candidate.version
        if other.decision_scope != version.decision_scope:
            continue
        if not all(
            (
                _dimensions_overlap(version.case_categories, other.case_categories),
                _dimensions_overlap(version.products, other.products),
                _dimensions_overlap(version.regions, other.regions),
                _dimensions_overlap(version.channels, other.channels),
                _dimensions_overlap(version.customer_tiers, other.customer_tiers),
            )
        ):
            continue
        if _time_windows_overlap(
            effective_from,
            version.effective_to,
            other.effective_from,
            other.effective_to,
        ):
            conflicts.append(candidate.policy.public_id)
    return sorted(set(conflicts))


def _dimensions_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
    left_values = set(left)
    right_values = set(right)
    return "all" in left_values or "all" in right_values or bool(left_values & right_values)


def _time_windows_overlap(
    left_from: datetime | None,
    left_to: datetime | None,
    right_from: datetime | None,
    right_to: datetime | None,
) -> bool:
    start = max(
        left_from or datetime.min.replace(tzinfo=UTC),
        right_from or datetime.min.replace(tzinfo=UTC),
    )
    end = min(
        left_to or datetime.max.replace(tzinfo=UTC),
        right_to or datetime.max.replace(tzinfo=UTC),
    )
    return start < end
