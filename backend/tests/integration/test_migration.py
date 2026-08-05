from sqlalchemy import String, inspect, text

from app.persistence.database import Database


def test_migration_creates_only_approved_core_tables(database: Database) -> None:
    inspector = inspect(database.engine)
    tables = set(inspector.get_table_names())

    assert {
        "alembic_version",
        "tasks",
        "requests",
        "agent_runs",
        "audit_events",
        "booking_snapshots",
        "customer_snapshots",
        "tool_attempts",
        "external_receipts",
        "risk_decisions",
        "proposal_versions",
        "policy_document_versions",
        "policy_chunks",
        "retrieval_evidence",
        "reviewer_reservations",
        "approval_decisions",
        "organizations",
        "memberships",
        "invitations",
        "cases",
        "case_requests",
        "case_customers",
        "business_object_snapshots",
        "conversation_threads",
        "conversation_messages",
        "response_drafts",
        "policies",
        "governed_policy_versions",
        "governed_policy_clauses",
        "case_policy_evidence",
        "case_analysis_generations",
        "case_analysis_runs",
        "case_analysis_checkpoints",
        "case_proposals",
        "case_proposal_versions",
        "proposal_evidence_bindings",
        "proposal_context_bindings",
        "case_proposed_actions",
        "proposal_response_drafts",
        "case_reviews",
        "case_review_snapshots",
        "case_review_reservations",
        "case_review_decisions",
        "connections",
        "connection_health_checks",
        "case_actions",
        "case_action_attempts",
        "case_action_receipts",
        "case_action_reconciliations",
        "organization_settings",
        "notifications",
        "notification_outbox",
        "case_data_governance",
        "case_quality_projections",
    } <= tables
    assert "bookings" not in tables
    assert "customers" not in tables

    policy_columns = {
        column["name"]: column for column in inspector.get_columns("policy_document_versions")
    }
    invitation_columns = {
        column["name"]: column for column in inspector.get_columns("invitations")
    }
    connection_columns = {
        column["name"]: column for column in inspector.get_columns("connections")
    }
    invitation_uniques = {
        constraint["name"] for constraint in inspector.get_unique_constraints("invitations")
    }
    policy_category_type = policy_columns["case_category"]["type"]
    provider_invitation_type = invitation_columns["provider_invitation_id"]["type"]
    runtime_fingerprint_type = connection_columns["runtime_config_fingerprint"]["type"]

    assert isinstance(policy_category_type, String)
    assert isinstance(provider_invitation_type, String)
    assert isinstance(runtime_fingerprint_type, String)
    assert policy_category_type.length == 64
    assert provider_invitation_type.length == 200
    assert runtime_fingerprint_type.length == 64
    assert "uq_invitations_provider_invitation" in invitation_uniques

    case_indexes = {index["name"] for index in inspector.get_indexes("cases")}
    policy_version_indexes = {
        index["name"] for index in inspector.get_indexes("governed_policy_versions")
    }
    clause_indexes = {
        index["name"] for index in inspector.get_indexes("governed_policy_clauses")
    }
    assert {
        "ix_cases_org_due_public",
        "ix_cases_org_updated_public",
        "ix_cases_org_priority_queue",
        "ix_cases_public_id_trgm",
        "ix_cases_external_reference_trgm",
        "ix_cases_issue_trgm",
    } <= case_indexes
    assert {
        "ix_policy_versions_case_categories_gin",
        "ix_policy_versions_products_gin",
        "ix_policy_versions_regions_gin",
        "ix_policy_versions_channels_gin",
        "ix_policy_versions_customer_tiers_gin",
    } <= policy_version_indexes
    assert "ix_policy_clauses_embedding_hnsw" in clause_indexes
    with database.engine.connect() as connection:
        assert connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")
        )
