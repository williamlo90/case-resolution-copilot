from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from inspect import getsource
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from sqlalchemy.orm import Session
from starlette.types import Scope

from app.api.routes import cases as case_routes
from app.api.routes import decision_briefs as decision_brief_routes
from app.api.schemas.decision_briefs import GenerateDecisionBriefRequest
from app.domain.decision_briefs import DecisionGenerationLease
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    AuthenticationMode,
    MemberRole,
)
from app.persistence.case_repository import CaseRepository
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.policy_repository import PolicyRepository
from app.services.decision_brief_service import DecisionBriefGenerationPlan
from tests.builders import valid_case_workspace, valid_evidence_result


class TrackedDatabase:
    def __init__(self) -> None:
        self.session_open = False
        self.session_count = 0
        self.session_value = object()

    @contextmanager
    def session(self) -> Iterator[object]:
        self.session_count += 1
        self.session_open = True
        try:
            yield self.session_value
        finally:
            self.session_open = False


def _actor() -> ActorContext:
    return ActorContext(
        actor_id="USR-0003",
        organization_id="ORG-0001",
        name="Ari Administrator",
        kind=ActorKind.MEMBER,
        role=MemberRole.ADMINISTRATOR,
        permissions=ROLE_PERMISSIONS[MemberRole.ADMINISTRATOR],
        authentication_mode=AuthenticationMode.DETERMINISTIC_DEVELOPMENT,
    )


def _request(
    *,
    database: object,
    auth_provider: object | None = None,
    decision_engine: object | None = None,
) -> Request:
    app = FastAPI()
    app.state.database = database
    app.state.auth_provider = auth_provider
    app.state.decision_engine = decision_engine
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
        "method": "GET",
        "root_path": "",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "app": app,
    }
    return Request(scope)


def test_case_response_is_built_while_database_session_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = TrackedDatabase()
    actor = _actor()

    class RecordingAuthProvider:
        def __init__(self) -> None:
            self.session: object | None = None

        def authenticate(
            self,
            actor_id: str | None,
            *,
            request: object | None = None,
            session: object | None = None,
        ) -> ActorContext:
            del actor_id, request
            self.session = session
            return actor

    provider = RecordingAuthProvider()
    request = _request(database=database, auth_provider=provider)
    projection = object()

    class FakeWorkspaceQuery:
        def get(self, **values: object) -> object:
            del values
            assert database.session_open
            return projection

    def present(
        value: object,
        *,
        organization_id: str,
    ) -> str:
        assert value is projection
        assert organization_id == actor.organization_id
        assert database.session_open
        return "case-payload"

    monkeypatch.setattr(
        case_routes,
        "_workspace_query",
        lambda session: FakeWorkspaceQuery() if session is database.session_value else None,
    )
    monkeypatch.setattr(case_routes, "present_case_workspace", present)
    monkeypatch.setattr(case_routes, "CaseDetailResponse", lambda *, data: data)

    dependency = case_routes._case_request_context(request, None)
    context = next(dependency)
    try:
        response = case_routes.get_case("CS-2048", request, context)
        assert database.session_open
        assert provider.session is context.session
    finally:
        with pytest.raises(StopIteration):
            next(dependency)

    assert str(response) == "case-payload"
    assert not database.session_open
    assert database.session_count == 1


def test_latest_decision_brief_uses_one_root_lookup(
    monkeypatch: object,
) -> None:
    row = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
    result = MagicMock()
    result.one_or_none.return_value = row
    session = MagicMock(spec=Session)
    session.execute.return_value = result
    session.scalar.return_value = None
    expected = MagicMock()
    repository = DecisionBriefRepository(session)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        repository._queries,
        "_assemble_brief",
        lambda **_: expected,
    )

    actual = repository.get_latest(
        organization_public_id="ORG-0001",
        case_public_id="CS-2048",
    )

    assert actual is expected
    session.execute.assert_called_once()
    session.scalar.assert_not_called()
    session.get.assert_not_called()


def test_policy_evidence_lookup_does_not_refetch_case_scope(
    monkeypatch: object,
) -> None:
    result = MagicMock()
    result.all.return_value = []
    session = MagicMock(spec=Session)
    session.execute.return_value = result
    repository = PolicyRepository(session)

    def fail_scope_lookup(*_: object, **__: object) -> object:
        raise AssertionError("case scope was fetched twice")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        repository,
        "_required_case",
        fail_scope_lookup,
    )

    assert (
        repository.list_evidence_for_case(
            organization_public_id="ORG-0001",
            case_public_id="CS-2048",
        )
        == []
    )
    session.execute.assert_called_once()


def test_case_workspace_loads_draft_in_the_root_query() -> None:
    source = getsource(CaseRepository.get_workspace)

    assert ".outerjoin(\n                ResponseDraftModel," in source
    assert "self._session.scalar(\n            select(ResponseDraftModel)" not in source


def test_case_workspace_detail_collections_are_bounded() -> None:
    workspace_source = getsource(CaseRepository.get_workspace)
    message_source = getsource(CaseRepository._conversation_page)
    activity_source = getsource(CaseRepository._activity_page)

    assert ".limit(CASE_WORKSPACE_BUSINESS_CONTEXT_LIMIT)" in workspace_source
    assert ".limit(limit + 1)" in message_source
    assert ".limit(limit + 1)" in activity_source
    assert "ConversationMessageModel.created_at.desc()" in message_source
    assert "AuditEventModel.occurred_at.desc()" in activity_source


def test_case_queue_reuses_the_authenticated_database_session() -> None:
    source = getsource(case_routes.list_cases)

    assert "CaseRepository(context.session)" in source
    assert "_database(request).session()" not in source


def test_case_queue_uses_keyset_boundaries_instead_of_database_offset() -> None:
    source = getsource(CaseRepository.list_cases)

    assert ".offset(" not in source
    assert "CaseQueueCursorDirection.BACKWARD" in source
    assert "CaseModel.public_id > position.public_id" in source
    assert "CaseModel.public_id < position.public_id" in source
    assert ".limit(limit + 1)" in source


def test_decision_brief_model_runs_between_two_database_transactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = TrackedDatabase()
    actor = _actor()
    events: list[str] = []
    preparation = DecisionBriefGenerationPlan(
        workspace=valid_case_workspace(),
        evidence=valid_evidence_result(),
        expected_case_version=1,
        input_fingerprint="f" * 64,
        context_fingerprint="c" * 64,
        evidence_fingerprint="e" * 64,
        lease=DecisionGenerationLease(
            input_fingerprint="f" * 64,
            owner_token=uuid4(),
            fence_token=1,
            attempt=1,
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        ),
    )
    analysis = object()
    persisted = object()

    class RecordingEngine:
        def analyze(self, **values: object) -> object:
            assert values == {
                "workspace": preparation.workspace,
                "evidence": preparation.evidence,
                "input_fingerprint": preparation.input_fingerprint,
            }
            assert not database.session_open
            events.append("analyze")
            return analysis

    class RecordingService:
        def __init__(self, *_: object) -> None:
            pass

        def prepare_generation(self, **values: object) -> object:
            assert values["actor"] is actor
            assert database.session_open
            events.append("prepare")
            return preparation

        def persist_generation(self, **values: object) -> object:
            assert values["actor"] is actor
            assert values["preparation"] is preparation
            assert values["analysis"] is analysis
            assert database.session_open
            events.append("persist")
            return persisted

    engine = RecordingEngine()
    request = _request(database=database, decision_engine=engine)
    request.state.correlation_id = "corr-transaction"
    monkeypatch.setattr(decision_brief_routes, "CaseRepository", lambda _: object())
    monkeypatch.setattr(decision_brief_routes, "PolicyRepository", lambda *_: object())
    monkeypatch.setattr(decision_brief_routes, "DecisionBriefRepository", lambda _: object())
    monkeypatch.setattr(decision_brief_routes, "PolicyEvidenceService", lambda *_: object())
    monkeypatch.setattr(decision_brief_routes, "DecisionBriefService", RecordingService)
    monkeypatch.setattr(
        decision_brief_routes,
        "present_decision_brief",
        lambda value, **_: "decision-brief" if value is persisted else "unexpected",
    )
    monkeypatch.setattr(
        decision_brief_routes,
        "DecisionBriefEnvelope",
        lambda *, data: data,
    )

    response = decision_brief_routes.generate_decision_brief(
        "CS-2048",
        GenerateDecisionBriefRequest(expected_case_version=1),
        request,
        actor,
    )

    assert str(response) == "decision-brief"
    assert events == ["prepare", "analyze", "persist"]
    assert database.session_count == 2
    assert not database.session_open
