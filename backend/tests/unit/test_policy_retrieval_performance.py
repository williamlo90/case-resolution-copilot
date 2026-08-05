from inspect import getsource

from app.persistence.policy_repository import PolicyRepository
from app.services.policy_evidence_service import PolicyEvidenceService


def test_governed_retrieval_architecture_remains_filtered_ranked_and_bounded() -> None:
    repository_source = getsource(PolicyRepository.search_retrieval_candidates)
    service_source = getsource(PolicyEvidenceService._resolve_bindings)

    assert ".limit(candidate_limit)" in repository_source
    assert "cosine_distance(query_embedding)" in repository_source
    assert "GovernedPolicyClauseModel.embedding_version" in repository_source
    assert "active_matches > candidate_limit" not in repository_source
    assert "conflicting_scopes" in repository_source
    assert "category_match" in repository_source
    assert "applicability_match" in repository_source
    assert "effective_match" in repository_source
    assert "list_candidates" not in service_source
    assert "_cosine_similarity" not in service_source
