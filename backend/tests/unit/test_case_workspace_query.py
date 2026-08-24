from unittest.mock import MagicMock
from uuid import uuid4

from app.api.presenters.cases import present_case_workspace
from app.domain.cases import CaseCollectionWindowRecord, CaseStatus, ResponseDraftRecord
from app.persistence.case_repository import CaseRepository
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.policy_repository import PolicyRepository
from app.persistence.review_repository import ReviewRepository
from app.security.authentication import DeterministicAuthProvider
from app.services.case_workspace_query import (
    CaseWorkspaceProjection,
    CaseWorkspaceQueryService,
)
from tests.builders import NOW, valid_case_workspace, valid_decision_brief


def test_workspace_query_uses_valid_models_and_server_owned_commands() -> None:
    workspace = valid_case_workspace()
    cases = MagicMock(spec=CaseRepository)
    cases.get_workspace.return_value = workspace
    decisions = MagicMock(spec=DecisionBriefRepository)
    decisions.get_latest.return_value = None
    policies = MagicMock(spec=PolicyRepository)
    policies.list_evidence_for_case.return_value = []
    reviews = MagicMock(spec=ReviewRepository)
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    projection = CaseWorkspaceQueryService(
        cases=cases,
        decisions=decisions,
        policies=policies,
        reviews=reviews,
    ).get(actor=actor, case_id=workspace.case.public_id)

    assert projection.workspace is workspace
    assert projection.brief is None
    assert projection.evidence == ()
    assert set(projection.available_commands) == {
        "assign_to_me",
        "send_reply",
        "add_note",
        "add_evidence",
        "start_investigation",
        "request_information",
        "revise_resolution",
        "save_draft",
    }
    reviews.get_for_proposal.assert_not_called()


def test_workspace_presentation_allows_imported_case_without_business_context() -> None:
    workspace = valid_case_workspace()
    workspace = workspace.model_copy(
        update={
            "business_contexts": [],
            "collections": workspace.collections.model_copy(
                update={
                    "business_contexts": CaseCollectionWindowRecord(
                        returned=0,
                        total=0,
                        has_more=False,
                    )
                }
            ),
        }
    )

    response = present_case_workspace(
        CaseWorkspaceProjection(
            workspace=workspace,
            brief=None,
            evidence=(),
            available_commands=(),
        ),
        organization_id="ORG-NORTHSTAR",
    )

    assert response.business_contexts == []
    assert response.collections.business_contexts.returned == 0
    assert response.collections.business_contexts.total == 0


def test_workspace_presentation_keeps_a_manually_saved_draft_authoritative() -> None:
    workspace = valid_case_workspace()
    workspace = workspace.model_copy(
        update={
            "draft": ResponseDraftRecord(
                id=uuid4(),
                public_id="DFT-MANUAL-0001",
                organization_id=workspace.case.organization_id,
                case_id=workspace.case.id,
                subject="Manual customer update",
                body="This wording was reviewed and saved by the operator.",
                status="draft",
                version=3,
                updated_at=NOW,
            )
        }
    )
    generated = valid_decision_brief()

    response = present_case_workspace(
        CaseWorkspaceProjection(
            workspace=workspace,
            brief=generated,
            evidence=(),
            available_commands=(),
        ),
        organization_id="ORG-NORTHSTAR",
    )

    assert response.response_draft is not None
    assert response.response_draft.id == "DFT-MANUAL-0001"
    assert response.response_draft.body == ("This wording was reviewed and saved by the operator.")
    assert response.response_draft.body != generated.response_draft.body


def test_workspace_hides_review_submission_when_case_changed_after_brief() -> None:
    workspace = valid_case_workspace()
    workspace = workspace.model_copy(
        update={
            "case": workspace.case.model_copy(
                update={"status": CaseStatus.INVESTIGATING, "version": 2}
            )
        }
    )
    cases = MagicMock(spec=CaseRepository)
    decisions = MagicMock(spec=DecisionBriefRepository)
    policies = MagicMock(spec=PolicyRepository)
    reviews = MagicMock(spec=ReviewRepository)
    decisions.get_latest.return_value = valid_decision_brief()
    policies.list_evidence_for_case.return_value = []
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    projection = CaseWorkspaceQueryService(
        cases=cases,
        decisions=decisions,
        policies=policies,
        reviews=reviews,
    ).project(actor=actor, workspace=workspace)

    assert "submit_for_review" not in projection.available_commands
    assert "revise_resolution" in projection.available_commands
    reviews.get_for_proposal.assert_not_called()
