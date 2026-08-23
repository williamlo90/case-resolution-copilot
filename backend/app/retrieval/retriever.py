from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.policies import PolicyDocumentVersionRecord, RetrievalEvidenceRecord
from app.persistence.database import Database
from app.persistence.models import (
    PolicyChunkModel,
    PolicyDocumentVersionModel,
    ProposalVersionModel,
    RetrievalEvidenceModel,
)
from app.retrieval.embeddings import embed
from app.retrieval.scoring import hybrid_relevance as _hybrid_relevance

RetrievalStatus = Literal["relevant", "missing", "stale", "conflicting", "inapplicable"]
RetrievalMatch = tuple[PolicyChunkModel, PolicyDocumentVersionModel, float]

RETRIEVAL_CANDIDATE_LIMIT = 20
RETRIEVAL_RESULT_LIMIT = 3
RETRIEVAL_SCORE_THRESHOLD = 0.15

@dataclass(frozen=True)
class RetrievalDecision:
    status: RetrievalStatus
    reason: str
    matches: list[RetrievalMatch]


class PolicyRetriever:
    def __init__(self, database: Database) -> None:
        self.database = database

    def retrieve_and_bind(
        self,
        *,
        proposal_id: UUID,
        query: str,
        case_category: str,
        plan: str,
        jurisdiction: str,
        customer_tier: str,
        as_of: date,
    ) -> list[RetrievalEvidenceRecord]:
        with self.database.session() as session:
            decision = self._decide(
                session=session,
                query=query,
                case_category=case_category,
                plan=plan,
                jurisdiction=jurisdiction,
                customer_tier=customer_tier,
                as_of=as_of,
            )
            if decision.status != "relevant":
                return []
            chunk, document, raw_distance = decision.matches[0]
            score = 1.0 - float(raw_distance)
            if score < RETRIEVAL_SCORE_THRESHOLD:
                return []
            evidence = RetrievalEvidenceModel(
                proposal_id=proposal_id,
                policy_version_id=document.id,
                chunk_id=chunk.id,
                source_id=document.source_id,
                clause=chunk.clause,
                excerpt=chunk.text,
                content_hash=chunk.content_hash,
                effective_from=document.effective_from,
                retrieval_score=score,
                corpus_version=document.corpus_version,
                chunking_version=chunk.chunking_version,
                embedding_version=chunk.embedding_version,
                index_version=chunk.index_version,
            )
            session.add(evidence)
            proposal = session.get(ProposalVersionModel, proposal_id)
            if proposal is None:
                raise LookupError(f"Proposal {proposal_id} does not exist.")
            proposal.status = "waiting_approval"
            session.flush()
            return [RetrievalEvidenceRecord.model_validate(evidence)]

    def decide(
        self,
        *,
        query: str,
        case_category: str,
        plan: str,
        jurisdiction: str,
        customer_tier: str,
        as_of: date,
    ) -> RetrievalDecision:
        with self.database.session() as session:
            return self._decide(
                session=session,
                query=query,
                case_category=case_category,
                plan=plan,
                jurisdiction=jurisdiction,
                customer_tier=customer_tier,
                as_of=as_of,
            )

    def _decide(
        self,
        *,
        session: Session,
        query: str,
        case_category: str,
        plan: str,
        jurisdiction: str,
        customer_tier: str,
        as_of: date,
    ) -> RetrievalDecision:
        distance = PolicyChunkModel.embedding.cosine_distance(embed(query))
        base = (
            select(PolicyChunkModel, PolicyDocumentVersionModel, distance.label("distance"))
            .join(
                PolicyDocumentVersionModel,
                PolicyDocumentVersionModel.id == PolicyChunkModel.policy_version_id,
            )
            .where(PolicyDocumentVersionModel.lifecycle_status == "active")
        )
        metadata = (
            PolicyDocumentVersionModel.case_category == case_category,
            PolicyDocumentVersionModel.plan.in_((plan, "all")),
            PolicyDocumentVersionModel.jurisdiction.in_((jurisdiction, "ALL")),
            PolicyDocumentVersionModel.customer_tier.in_((customer_tier, "all")),
        )
        raw_candidates = session.execute(
            base.where(*metadata).order_by(distance).limit(RETRIEVAL_CANDIDATE_LIMIT)
        ).all()
        candidates = sorted(
            (
                (
                    chunk,
                    document,
                    1.0 - _hybrid_relevance(query, chunk.text, float(raw_distance)),
                )
                for chunk, document, raw_distance in raw_candidates
            ),
            key=lambda row: (row[2], row[1].source_id, row[0].clause),
        )
        active = [
            row
            for row in candidates
            if row[1].effective_from <= as_of
            and (row[1].effective_to is None or row[1].effective_to >= as_of)
        ]
        if len({row[1].id for row in active}) > 1:
            return RetrievalDecision("conflicting", "Multiple active policy versions apply.", [])
        if active:
            score = 1.0 - float(active[0][2])
            if score >= RETRIEVAL_SCORE_THRESHOLD:
                return RetrievalDecision(
                    "relevant",
                    "Applicable policy evidence found.",
                    active[:RETRIEVAL_RESULT_LIMIT],
                )
        if candidates:
            return RetrievalDecision(
                "stale",
                "Matching policy exists but is outside its effective dates.",
                [],
            )
        category_rows = session.execute(
            base.where(PolicyDocumentVersionModel.case_category == case_category).limit(1)
        ).all()
        if category_rows:
            return RetrievalDecision(
                "inapplicable", "Policy metadata does not match this case.", []
            )
        return RetrievalDecision("missing", "No policy exists for this case category.", [])

    def list_for_proposal(self, proposal_id: UUID) -> list[RetrievalEvidenceRecord]:
        with self.database.session() as session:
            rows = session.scalars(
                select(RetrievalEvidenceModel).where(
                    RetrievalEvidenceModel.proposal_id == proposal_id
                )
            )
            return [RetrievalEvidenceRecord.model_validate(row) for row in rows]

    def get_policy(self, source_id: str, version: int) -> PolicyDocumentVersionRecord | None:
        with self.database.session() as session:
            model = session.scalar(
                select(PolicyDocumentVersionModel).where(
                    PolicyDocumentVersionModel.source_id == source_id,
                    PolicyDocumentVersionModel.version == version,
                )
            )
            return PolicyDocumentVersionRecord.model_validate(model) if model else None
