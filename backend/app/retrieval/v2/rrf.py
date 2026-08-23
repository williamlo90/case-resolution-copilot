from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.policies import PolicyCandidateRecord
from app.domain.retrieval_v2 import RankedClause

RRF_ALGORITHM_VERSION = "policy-hybrid-rrf-v2"
RRF_CONSTANT = 60


@dataclass(slots=True)
class _Accumulator:
    candidate: PolicyCandidateRecord
    dense_rank: int | None = None
    lexical_rank: int | None = None
    score: float = 0.0


def fuse_rankings(
    *,
    dense: Sequence[PolicyCandidateRecord],
    lexical: Sequence[PolicyCandidateRecord],
) -> list[RankedClause]:
    accumulated: dict[UUID, _Accumulator] = {}
    _accumulate(accumulated, dense, source="dense")
    _accumulate(accumulated, lexical, source="lexical")
    ranked = [
        RankedClause(
            candidate=item.candidate,
            dense_rank=item.dense_rank,
            lexical_rank=item.lexical_rank,
            fused_score=item.score,
        )
        for item in accumulated.values()
    ]
    return sorted(
        ranked,
        key=lambda item: (
            -item.fused_score,
            item.candidate.policy.public_id,
            -item.candidate.version.version,
            item.candidate.clauses[0].sequence,
        ),
    )


def select_diverse(
    ranked: Sequence[RankedClause],
    *,
    limit: int = 3,
    per_policy_limit: int = 2,
) -> list[RankedClause]:
    if limit < 1 or per_policy_limit < 1:
        raise ValueError("Retrieval limits must be positive.")
    policy_ids = {item.candidate.policy.id for item in ranked}
    effective_policy_limit = limit if len(policy_ids) <= 1 else per_policy_limit
    selected: list[RankedClause] = []
    counts: dict[UUID, int] = {}
    for item in ranked:
        policy_id = item.candidate.policy.id
        if counts.get(policy_id, 0) >= effective_policy_limit:
            continue
        selected.append(item)
        counts[policy_id] = counts.get(policy_id, 0) + 1
        if len(selected) == limit:
            break
    return selected


def _accumulate(
    target: dict[UUID, _Accumulator],
    ranking: Sequence[PolicyCandidateRecord],
    *,
    source: Literal["dense", "lexical"],
) -> None:
    for rank, candidate in enumerate(ranking, start=1):
        if len(candidate.clauses) != 1:
            raise ValueError("Each ranking item must contain exactly one clause.")
        clause_id = candidate.clauses[0].id
        item = target.setdefault(clause_id, _Accumulator(candidate=candidate))
        item.score += 1 / (RRF_CONSTANT + rank)
        if source == "dense":
            item.dense_rank = rank
        else:
            item.lexical_rank = rank
