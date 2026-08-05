from scripts.check_case_transport_contract import (
    CONTRACT_MODELS,
    contract_matches,
)


def test_committed_case_transport_contract_matches_backend_models() -> None:
    assert set(CONTRACT_MODELS) == {
        "CaseListResponse",
        "CaseDetailResponse",
        "ConversationMessagePageResponse",
        "CaseActivityPageResponse",
    }
    assert contract_matches()
