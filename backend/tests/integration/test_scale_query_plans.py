from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.persistence.database import Database
from app.persistence.models import (
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    PolicyModel,
)
from app.persistence.policy_repository import PolicyRepository
from app.retrieval.embeddings import EMBEDDING_VERSION, embed

POLICY_SCALE_ROW_COUNT = 10_000
CASE_SCALE_ROW_COUNT = 50_000
POLICY_TOP_K = 16
CASE_PAGE_LIMIT = 21
MAX_DATABASE_EXECUTION_MS = 1_000.0
MAX_SHARED_BLOCKS = 8_000
MAX_PLAN_ROWS_VISITED = 512


def test_scale_queries_use_bounded_index_plans(database: Database) -> None:
    organization_id, organization_public_id = _seed_scale_fixture(database)
    policy_plan = _exercise_policy_query(
        database,
        organization_public_id=organization_public_id,
    )
    queue_plans = _case_queue_plans(database, organization_id=organization_id)

    policy_metrics = _assert_plan(
        policy_plan,
        expected_indexes={"ix_policy_clauses_embedding_hnsw"},
        maximum_rows=POLICY_TOP_K,
    )
    queue_metrics = {
        "priority": _assert_plan(
            queue_plans["priority"],
            expected_indexes={"ix_cases_org_priority_queue"},
            maximum_rows=CASE_PAGE_LIMIT,
        ),
        "sla": _assert_plan(
            queue_plans["sla"],
            expected_indexes={"ix_cases_org_due_public"},
            maximum_rows=CASE_PAGE_LIMIT,
        ),
        "updated": _assert_plan(
            queue_plans["updated"],
            expected_indexes={"ix_cases_org_updated_public"},
            maximum_rows=CASE_PAGE_LIMIT,
        ),
        "contains_search": _assert_plan(
            queue_plans["contains_search"],
            expected_indexes={
                "ix_cases_public_id_trgm",
                "ix_cases_external_reference_trgm",
                "ix_cases_issue_trgm",
                "ix_case_customers_name_trgm",
            },
            maximum_rows=CASE_PAGE_LIMIT,
            require_any_index=True,
        ),
    }
    print(
        json.dumps(
            {
                "policy_fixture_rows": POLICY_SCALE_ROW_COUNT,
                "case_fixture_rows": CASE_SCALE_ROW_COUNT,
                "policy_top_k": POLICY_TOP_K,
                "policy": policy_metrics,
                "queue": queue_metrics,
            },
            sort_keys=True,
        )
    )


def _seed_scale_fixture(database: Database) -> tuple[UUID, str]:
    organization_id = uuid4()
    membership_id = uuid4()
    policy_id = uuid4()
    policy_version_id = uuid4()
    organization_public_id = "ORG-QUERY-PLAN"
    now = datetime.now(UTC)
    with database.session() as session:
        session.add(
            OrganizationModel(
                id=organization_id,
                public_id=organization_public_id,
                name="Disposable query plan organization",
                slug=f"query-plan-{organization_id.hex[:12]}",
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            MembershipModel(
                id=membership_id,
                public_id="USR-QUERY-PLAN",
                organization_id=organization_id,
                subject_id=f"query-plan-{membership_id}",
                name="Query Plan Owner",
                email=f"query-plan-{membership_id.hex[:12]}@example.invalid",
                role="administrator",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            PolicyModel(
                id=policy_id,
                public_id="POL-QUERY-PLAN",
                organization_id=organization_id,
                title="Scale retrieval policy",
                description="Synthetic policy used only on a disposable database branch.",
                status="published",
                owner_id=membership_id,
                source_kind="manual",
                source_name="query-plan-fixture",
                current_version=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            GovernedPolicyVersionModel(
                id=policy_version_id,
                public_id="POLV-QUERY-PLAN",
                organization_id=organization_id,
                policy_id=policy_id,
                version=1,
                record_version=1,
                status="published",
                immutable=True,
                source_text="Synthetic scale fixture.",
                content_hash="a" * 64,
                decision_scope="scale_fixture_resolution",
                case_categories=["billing_dispute"],
                products=["all"],
                regions=["all"],
                channels=["all"],
                customer_tiers=["all"],
                effective_from=None,
                effective_to=None,
                created_by="USR-QUERY-PLAN",
                created_at=now,
                published_at=now,
            )
        )
        session.flush()
        session.execute(
            text(
                """
                INSERT INTO governed_policy_clauses (
                    id,
                    public_id,
                    organization_id,
                    policy_id,
                    policy_version_id,
                    sequence,
                    heading,
                    text,
                    applies_when,
                    content_hash,
                    chunking_version,
                    embedding_version,
                    index_version,
                    embedding
                )
                SELECT
                    gen_random_uuid(),
                    'POLC-QP-' || lpad(g::text, 5, '0'),
                    :organization_id,
                    :policy_id,
                    :policy_version_id,
                    g,
                    'Scale clause ' || g,
                    'Synthetic bounded retrieval clause ' || g,
                    'billing dispute',
                    md5(g::text) || md5('clause-' || g::text),
                    'governed-clause-v1',
                    :embedding_version,
                    'governed-policy-index-v1',
                    (
                        '[' ||
                        sin(g::double precision)::text ||
                        ',' ||
                        cos(g::double precision)::text ||
                        repeat(',0', 30) ||
                        ']'
                    )::vector
                FROM generate_series(1, :row_count) AS g
                """
            ),
            {
                "organization_id": organization_id,
                "policy_id": policy_id,
                "policy_version_id": policy_version_id,
                "embedding_version": EMBEDDING_VERSION,
                "row_count": POLICY_SCALE_ROW_COUNT,
            },
        )
        session.execute(
            text(
                """
                WITH inserted_cases AS (
                    INSERT INTO cases (
                        id,
                        public_id,
                        organization_id,
                        source_id,
                        external_reference,
                        category,
                        issue,
                        status,
                        owner_id,
                        urgency,
                        risk,
                        due_at,
                        source_freshness,
                        version,
                        created_at,
                        updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        'CASE-QP-' || lpad(g::text, 5, '0'),
                        :organization_id,
                        'SOURCE-QP-' || lpad(g::text, 5, '0'),
                        CASE
                            WHEN g = 9973 THEN 'REF-NEEDLE-009973'
                            ELSE 'REF-QP-' || lpad(g::text, 5, '0')
                        END,
                        'billing_dispute',
                        'Synthetic queue issue ' || g,
                        CASE WHEN g % 11 = 0 THEN 'needs_review' ELSE 'investigating' END,
                        :membership_id,
                        CASE WHEN g % 7 = 0 THEN 'high' ELSE 'medium' END,
                        CASE
                            WHEN g % 9 = 0 THEN 'high'
                            WHEN g % 3 = 0 THEN 'medium'
                            ELSE 'low'
                        END,
                        :now + make_interval(secs => g),
                        'current',
                        1,
                        :now - make_interval(secs => g),
                        :now - make_interval(secs => g)
                    FROM generate_series(1, :row_count) AS g
                    RETURNING id, organization_id, public_id
                )
                INSERT INTO case_customers (
                    id,
                    organization_id,
                    case_id,
                    customer_id,
                    name,
                    tier,
                    locale,
                    contact,
                    captured_at
                )
                SELECT
                    gen_random_uuid(),
                    organization_id,
                    id,
                    'CUSTOMER-' || public_id,
                    'Scale Customer ' || public_id,
                    'standard',
                    'en-US',
                    lower(public_id) || '@example.invalid',
                    :now
                FROM inserted_cases
                """
            ),
            {
                "organization_id": organization_id,
                "membership_id": membership_id,
                "now": now,
                "row_count": CASE_SCALE_ROW_COUNT,
            },
        )
        session.execute(text("ANALYZE governed_policy_clauses"))
        session.execute(text("ANALYZE governed_policy_versions"))
        session.execute(text("ANALYZE cases"))
        session.execute(text("ANALYZE case_customers"))
    return organization_id, organization_public_id


def _exercise_policy_query(
    database: Database,
    *,
    organization_public_id: str,
) -> dict[str, Any]:
    captured: list[tuple[str, Any]] = []

    def capture_statement(
        _connection: Any,
        _cursor: Any,
        statement: str,
        parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        if (
            "governed_policy_clauses.embedding" in statement
            and "<=>" in statement
            and statement.lstrip().upper().startswith("SELECT")
        ):
            captured.append((statement, parameters))

    event.listen(database.engine, "before_cursor_execute", capture_statement)
    try:
        with database.session() as session:
            result = PolicyRepository(session).search_retrieval_candidates(
                organization_public_id=organization_public_id,
                case_category="billing_dispute",
                products={"product-a"},
                region="us",
                channel="email",
                customer_tier="standard",
                as_of=datetime.now(UTC),
                query_embedding=embed("refund for a disputed charge"),
                embedding_version=EMBEDDING_VERSION,
                candidate_limit=POLICY_TOP_K,
            )
            assert result.active_matches == 1
            assert result.conflicting_scopes == []
            assert 0 < len(result.candidates) <= POLICY_TOP_K
    finally:
        event.remove(database.engine, "before_cursor_execute", capture_statement)

    assert len(captured) == 1
    statement, parameters = captured[0]
    with database.session() as session:
        payload = (
            session.connection()
            .exec_driver_sql(
                f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {statement}",
                parameters,
            )
            .scalar_one()
        )
    return _explain_document(payload)


def _case_queue_plans(
    database: Database,
    *,
    organization_id: UUID,
) -> dict[str, dict[str, Any]]:
    base_select = """
        SELECT cases.id
        FROM cases
        JOIN case_customers
          ON case_customers.organization_id = cases.organization_id
         AND case_customers.case_id = cases.id
        WHERE cases.organization_id = :organization_id
          AND cases.updated_at <= :snapshot_at
    """
    queries = {
        "priority": (
            base_select
            + """
              ORDER BY
                CASE
                    WHEN cases.risk = 'high' THEN 0
                    WHEN cases.risk = 'medium' THEN 1
                    ELSE 2
                END,
                cases.due_at,
                cases.public_id
              LIMIT 21
            """
        ),
        "sla": (
            base_select
            + """
              ORDER BY cases.due_at, cases.public_id
              LIMIT 21
            """
        ),
        "updated": (
            base_select
            + """
              ORDER BY cases.updated_at DESC, cases.public_id
              LIMIT 21
            """
        ),
        "contains_search": (
            base_select
            + """
              AND cases.id IN (
                SELECT searchable_cases.id
                FROM cases AS searchable_cases
                WHERE searchable_cases.organization_id = :organization_id
                  AND searchable_cases.public_id ILIKE :term
                UNION
                SELECT searchable_cases.id
                FROM cases AS searchable_cases
                WHERE searchable_cases.organization_id = :organization_id
                  AND searchable_cases.external_reference ILIKE :term
                UNION
                SELECT searchable_cases.id
                FROM cases AS searchable_cases
                WHERE searchable_cases.organization_id = :organization_id
                  AND searchable_cases.issue ILIKE :term
                UNION
                SELECT searchable_customers.case_id
                FROM case_customers AS searchable_customers
                WHERE searchable_customers.organization_id = :organization_id
                  AND searchable_customers.name ILIKE :term
              )
              ORDER BY cases.updated_at DESC, cases.public_id
              LIMIT 21
            """
        ),
    }
    parameters = {
        "organization_id": organization_id,
        "snapshot_at": datetime.now(UTC),
        "term": "%needle-009973%",
    }
    with database.session() as session:
        return {name: _explain(session, query, parameters) for name, query in queries.items()}


def _explain(
    session: Session,
    query: str,
    parameters: Mapping[str, object],
) -> dict[str, Any]:
    payload = session.execute(
        text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"),
        parameters,
    ).scalar_one()
    return _explain_document(payload)


def _explain_document(payload: object) -> dict[str, Any]:
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert isinstance(payload, list) and payload
    document = payload[0]
    assert isinstance(document, dict)
    return document


def _assert_plan(
    document: dict[str, Any],
    *,
    expected_indexes: set[str],
    maximum_rows: int,
    require_any_index: bool = False,
) -> dict[str, object]:
    plan = document["Plan"]
    assert isinstance(plan, dict)
    indexes = _index_names(plan)
    if not indexes & expected_indexes:
        print(
            json.dumps(
                {
                    "expected_indexes": sorted(expected_indexes),
                    "plan_nodes": _plan_node_metrics(plan),
                },
                sort_keys=True,
            )
        )
    if require_any_index:
        assert indexes & expected_indexes
    else:
        assert expected_indexes <= indexes
    actual_rows = int(plan.get("Actual Rows", 0))
    rows_visited = _rows_visited(plan)
    execution_ms = float(document.get("Execution Time", 0.0))
    shared_blocks = int(plan.get("Shared Hit Blocks", 0)) + int(plan.get("Shared Read Blocks", 0))
    assert actual_rows <= maximum_rows
    if rows_visited > MAX_PLAN_ROWS_VISITED:
        print(
            json.dumps(
                {
                    "rows_visited": rows_visited,
                    "plan_nodes": _plan_node_metrics(plan),
                },
                sort_keys=True,
            )
        )
    assert rows_visited <= MAX_PLAN_ROWS_VISITED
    assert execution_ms <= MAX_DATABASE_EXECUTION_MS
    assert shared_blocks <= MAX_SHARED_BLOCKS
    return {
        "actual_rows": actual_rows,
        "execution_ms": execution_ms,
        "indexes": sorted(indexes),
        "rows_visited": rows_visited,
        "shared_blocks": shared_blocks,
    }


def _index_names(node: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    index_name = node.get("Index Name")
    if isinstance(index_name, str):
        names.add(index_name)
    children = node.get("Plans", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                names.update(_index_names(child))
    return names


def _rows_visited(node: Mapping[str, Any]) -> int:
    rows = int(node.get("Actual Rows", 0)) * int(node.get("Actual Loops", 1))
    children = node.get("Plans", [])
    if isinstance(children, list):
        rows += sum(_rows_visited(child) for child in children if isinstance(child, dict))
    return rows


def _plan_node_metrics(node: Mapping[str, Any]) -> list[dict[str, object]]:
    metrics = [
        {
            "node": node.get("Node Type"),
            "index": node.get("Index Name"),
            "actual_rows": node.get("Actual Rows"),
            "actual_loops": node.get("Actual Loops"),
            "rows_removed_by_filter": node.get("Rows Removed by Filter"),
        }
    ]
    children = node.get("Plans", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                metrics.extend(_plan_node_metrics(child))
    return metrics
