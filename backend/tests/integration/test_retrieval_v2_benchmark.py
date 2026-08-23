from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.retrieval_v2_benchmark import run_frozen_retrieval_v2_benchmark
from app.evaluation.retrieval_v2_contract import load_frozen_retrieval_benchmark
from app.integrations.policy_source_simulator import DeterministicPolicySourceSimulator
from app.persistence.database import Database
from app.persistence.models import MembershipModel, OrganizationModel
from app.persistence.policy_indexing import SqlAlchemyPolicyIndexUnitOfWorkFactory
from app.persistence.policy_repository import PolicyRepository
from app.retrieval.v2.embeddings import deterministic_policy_embedding_provider
from app.security.authentication import DeterministicAuthProvider
from app.services.policy_indexing import PolicyIndexingService
from app.services.policy_service import PolicyService


def test_deterministic_retrieval_v2_meets_gate_on_postgresql(
    database: Database,
) -> None:
    assert _seed_governed_policies(database) == 4
    provider = deterministic_policy_embedding_provider()
    indexing = PolicyIndexingService(
        unit_of_work=SqlAlchemyPolicyIndexUnitOfWorkFactory(database),
        embedding_provider=provider,
        profile_key=provider.version,
        job_limit=16,
        page_budget=64,
    )

    indexing_result = indexing.drain(worker_id="phase7-integration")

    assert indexing_result.failed_jobs == 0
    assert indexing_result.completed_jobs == 4
    assert indexing_result.indexed_clauses == 8

    benchmark_root = Path(__file__).resolve().parents[2] / "evaluations" / "retrieval_v2"
    benchmark = load_frozen_retrieval_benchmark(benchmark_root)
    report = run_frozen_retrieval_v2_benchmark(
        database=database,
        benchmark=benchmark,
        openai_provider=None,
        query_character_limit=2_000,
    )
    v2 = next(profile for profile in report.profiles if profile.retrieval_generation == "v2")

    assert v2.metrics.gate_passed
    assert v2.metrics.recall_at_3 >= 0.90
    assert v2.metrics.wrong_version_count == 0
    assert v2.metrics.unsupported_citation_count == 0
    assert v2.metrics.cross_tenant_result_count == 0
    assert v2.metrics.failure_state_accuracy == 1.0


def _seed_governed_policies(database: Database) -> int:
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    assert actor.role is not None
    seeds = DeterministicPolicySourceSimulator().fetch_policies()
    with database.session() as session:
        organization = OrganizationModel(
            public_id=actor.organization_id,
            name="Phase 7 synthetic workspace",
            slug="phase7-synthetic-workspace",
        )
        session.add(organization)
        session.flush()
        session.add(
            MembershipModel(
                public_id=actor.actor_id,
                organization_id=organization.id,
                subject_id=actor.actor_id,
                name=actor.name,
                email="phase7-administrator@example.invalid",
                role=actor.role.value,
                status="active",
            )
        )
        session.flush()
        repository = PolicyRepository(session)
        service = PolicyService(repository)
        for seed in seeds:
            workspace = service.create_policy(
                actor=actor,
                title=seed.title,
                description=seed.description,
                source_kind=seed.source_kind,
                source_name=seed.source_name,
                source_text=seed.source_text,
                applicability=seed.applicability,
                effective_from=seed.effective_from,
                effective_to=None,
                public_id=seed.public_id,
                correlation_id=f"phase7-seed:{seed.public_id}",
            )
            workspace = service.submit_review(
                actor=actor,
                policy_id=seed.public_id,
                version_number=1,
                expected_policy_version=workspace.policy.version,
                expected_version=workspace.versions[0].version.record_version,
                correlation_id=f"phase7-seed:{seed.public_id}",
            )
            service.publish(
                actor=actor,
                policy_id=seed.public_id,
                version_number=1,
                expected_policy_version=workspace.policy.version,
                expected_version=workspace.versions[0].version.record_version,
                effective_from=seed.effective_from,
                correlation_id=f"phase7-seed:{seed.public_id}",
                now=datetime(2026, 7, 22, tzinfo=UTC),
            )
    return len(seeds)
