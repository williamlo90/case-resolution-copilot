from sqlalchemy import Index

from app.persistence.models.cases import CaseCustomerModel, CaseModel
from app.persistence.models.policies import (
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
)
from app.persistence.models.policy_retrieval_v2 import PolicyEmbeddingProfileModel


def _indexes(model: type[object]) -> dict[str, Index]:
    table = model.__table__  # type: ignore[attr-defined]
    return {index.name: index for index in table.indexes if index.name is not None}


def test_case_queue_and_search_indexes_are_declared_in_metadata() -> None:
    case_indexes = _indexes(CaseModel)
    customer_indexes = _indexes(CaseCustomerModel)

    assert {
        "ix_cases_org_due_public",
        "ix_cases_org_updated_public",
        "ix_cases_org_priority_queue",
        "ix_cases_public_id_trgm",
        "ix_cases_external_reference_trgm",
        "ix_cases_issue_trgm",
    } <= case_indexes.keys()
    assert "ix_case_customers_name_trgm" in customer_indexes
    assert case_indexes["ix_cases_public_id_trgm"].dialect_options["postgresql"]["using"] == "gin"
    assert (
        customer_indexes["ix_case_customers_name_trgm"].dialect_options["postgresql"]["ops"]["name"]
        == "gin_trgm_ops"
    )


def test_policy_retrieval_indexes_are_declared_in_metadata() -> None:
    version_indexes = _indexes(GovernedPolicyVersionModel)
    clause_indexes = _indexes(GovernedPolicyClauseModel)

    assert {
        "ix_policy_versions_case_categories_gin",
        "ix_policy_versions_products_gin",
        "ix_policy_versions_regions_gin",
        "ix_policy_versions_channels_gin",
        "ix_policy_versions_customer_tiers_gin",
    } <= version_indexes.keys()
    assert (
        version_indexes["ix_policy_versions_case_categories_gin"].dialect_options["postgresql"][
            "ops"
        ]["case_categories"]
        == "jsonb_path_ops"
    )
    assert (
        clause_indexes["ix_policy_clauses_embedding_hnsw"].dialect_options["postgresql"]["using"]
        == "hnsw"
    )


def test_policy_v2_active_profile_index_is_declared_in_metadata() -> None:
    active_profile = _indexes(PolicyEmbeddingProfileModel)[
        "uq_policy_embedding_profiles_active_environment"
    ]

    assert active_profile.unique
    assert str(active_profile.dialect_options["postgresql"]["where"]) == "status = 'active'"
