from unittest.mock import MagicMock

from app.persistence.case_repository import CaseRepository
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.policy_repository import PolicyRepository
from app.persistence.review_repository import ReviewRepository
from app.security.authentication import DeterministicAuthProvider
from app.services.case_workspace_query import CaseWorkspaceQueryService
from tests.builders import valid_case_workspace


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
        "request_information",
        "revise_resolution",
        "save_draft",
    }
    reviews.get_for_proposal.assert_not_called()
