from app.persistence.models import (
    CaseAnalysisCheckpointModel,
    CaseAnalysisRunModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseProposedActionModel,
    ProposalContextBindingModel,
    ProposalEvidenceBindingModel,
    ProposalResponseDraftModel,
)


def test_decision_brief_tables_are_generic_and_tenant_scoped() -> None:
    tables = [
        CaseAnalysisRunModel.__table__,
        CaseAnalysisCheckpointModel.__table__,
        CaseProposalModel.__table__,
        CaseProposalVersionModel.__table__,
        ProposalEvidenceBindingModel.__table__,
        ProposalContextBindingModel.__table__,
        CaseProposedActionModel.__table__,
        ProposalResponseDraftModel.__table__,
    ]

    for table in tables:
        assert "organization_id" in table.c
        assert "case_id" in table.c
        assert not ({"booking_id", "passenger_id", "airline"} & set(table.c.keys()))


def test_proposal_snapshot_keeps_exact_context_evidence_and_rule_versions() -> None:
    proposal_columns = set(CaseProposalVersionModel.__table__.c.keys())
    assert {
        "analysis_run_id",
        "immutable",
        "facts",
        "missing_information",
        "risks",
        "evidence_fingerprint",
        "context_fingerprint",
        "risk_fingerprint",
        "risk_rule_version",
        "model_version",
        "prompt_version",
        "graph_version",
    } <= proposal_columns
    assert {"evidence_id", "evidence_fingerprint"} <= set(
        ProposalEvidenceBindingModel.__table__.c.keys()
    )
    assert {"context_id", "snapshot_version", "context_fingerprint"} <= set(
        ProposalContextBindingModel.__table__.c.keys()
    )


def test_checkpoints_store_safe_summaries_not_raw_reasoning() -> None:
    columns = set(CaseAnalysisCheckpointModel.__table__.c.keys())

    assert {"step", "status", "summary", "input_fingerprint", "output_fingerprint"} <= columns
    assert {"prompt", "raw_payload", "reasoning", "chain_of_thought"}.isdisjoint(columns)
