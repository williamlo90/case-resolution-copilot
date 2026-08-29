from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.retrieval_v2_contract import RetrievalBenchmarkCase


class Wave1RagClauseFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    public_id: str = Field(pattern=r"^POLC-[A-Z0-9-]+$", max_length=64)
    heading: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=20, max_length=4000)


class Wave1RagSourceFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    public_id: str = Field(pattern=r"^POL-[A-Z0-9-]+$", max_length=64)
    title: str = Field(min_length=1, max_length=300)
    decision_scope: str = Field(min_length=1, max_length=100)
    case_categories: tuple[str, ...] = Field(min_length=1)
    products: tuple[str, ...] = Field(default=("all",), min_length=1)
    regions: tuple[str, ...] = Field(default=("all",), min_length=1)
    channels: tuple[str, ...] = Field(default=("all",), min_length=1)
    customer_tiers: tuple[str, ...] = Field(default=("all",), min_length=1)
    effective_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    effective_to: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    clauses: tuple[Wave1RagClauseFixture, ...] = Field(min_length=1)


class Wave1RagCaseFixture(RetrievalBenchmarkCase):
    expected_status: EvidenceRetrievalStatus
    expected_source_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_expected_sources_for_relevant_cases(self) -> Self:
        if self.expected_status is EvidenceRetrievalStatus.RELEVANT:
            if not self.expected_source_ids:
                raise ValueError("Relevant Wave 1 RAG cases require expected source IDs.")
        elif self.expected_source_ids:
            raise ValueError("Failure-state Wave 1 RAG cases cannot expect sources.")
        return self


class Wave1RagFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["wave1-rag-fixture-v1"]
    source: Literal["synthetic_credential_free_corpus"]
    sources: tuple[Wave1RagSourceFixture, ...] = Field(min_length=1)
    cases: tuple[Wave1RagCaseFixture, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_and_known_references(self) -> Self:
        source_ids = [source.public_id for source in self.sources]
        clause_ids = [clause.public_id for source in self.sources for clause in source.clauses]
        case_ids = [case.id for case in self.cases]
        for name, values in (
            ("policy", source_ids),
            ("clause", clause_ids),
            ("case", case_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Wave 1 RAG {name} IDs must be unique.")
        known = set(clause_ids)
        unknown = sorted(
            source_id
            for case in self.cases
            for source_id in case.expected_source_ids
            if source_id not in known
        )
        if unknown:
            raise ValueError(f"Wave 1 RAG cases reference unknown sources: {unknown}.")
        return self


def load_wave1_rag_fixture(path: Path) -> Wave1RagFixture:
    return Wave1RagFixture.model_validate_json(path.read_text(encoding="utf-8"))
