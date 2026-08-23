import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from app.domain.cases import CaseWorkspaceRecord
from app.domain.identity import ActorContext
from app.domain.policies import EvidenceRetrievalStatus, PolicyEvidenceBinding

RetrievalMode = Literal["v1", "v2_shadow", "v2"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievalResolution:
    status: EvidenceRetrievalStatus
    reason: str
    bindings: list[PolicyEvidenceBinding]


class PolicyRetrievalImplementation(Protocol):
    def resolve(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        as_of: datetime,
        correlation_id: str,
    ) -> RetrievalResolution: ...


class GovernedPolicyRetrievalFacade:
    def __init__(
        self,
        *,
        v1: PolicyRetrievalImplementation,
        v2: PolicyRetrievalImplementation | None = None,
        mode: RetrievalMode = "v1",
    ) -> None:
        if mode != "v1" and v2 is None:
            raise ValueError("RAG V2 mode requires a V2 retrieval implementation.")
        self._v1 = v1
        self._v2 = v2
        self._mode = mode

    def resolve(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        as_of: datetime,
        correlation_id: str,
    ) -> RetrievalResolution:
        if self._mode == "v1":
            return self._v1.resolve(
                actor=actor,
                workspace=workspace,
                as_of=as_of,
                correlation_id=correlation_id,
            )
        if self._mode == "v2":
            assert self._v2 is not None
            return self._v2.resolve(
                actor=actor,
                workspace=workspace,
                as_of=as_of,
                correlation_id=correlation_id,
            )
        v1_result = self._v1.resolve(
            actor=actor,
            workspace=workspace,
            as_of=as_of,
            correlation_id=correlation_id,
        )
        assert self._v2 is not None
        try:
            v2_result = self._v2.resolve(
                actor=actor,
                workspace=workspace,
                as_of=as_of,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.warning(
                "policy_retrieval_v2_shadow_failed",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(exc).__name__,
                    "v1_status": v1_result.status.value,
                },
            )
        else:
            logger.info(
                "policy_retrieval_v2_shadow_observed",
                extra={
                    "correlation_id": correlation_id,
                    "v1_status": v1_result.status.value,
                    "v1_binding_count": len(v1_result.bindings),
                    "v2_status": v2_result.status.value,
                    "v2_binding_count": len(v2_result.bindings),
                },
            )
        return v1_result
