from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cases import CaseCategory, CustomerTier, RequestChannel
from app.domain.policies import EvidenceRetrievalStatus

BenchmarkLane = Literal["release_corpus", "guard_contract"]


class GuardScopeFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index_ready: bool
    category_matches: int = Field(ge=0)
    applicable_matches: int = Field(ge=0)
    active_matches: int = Field(ge=0)
    conflicting_scopes: tuple[str, ...] = ()


class RetrievalBenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^RAG2-\d{3}$")
    lane: BenchmarkLane
    organization_public_id: str = Field(pattern=r"^ORG-[A-Z0-9-]+$", max_length=32)
    category: CaseCategory
    issue: str = Field(min_length=1, max_length=500)
    request_summary: str = Field(min_length=1, max_length=1000)
    products: tuple[str, ...] = Field(min_length=1)
    region: str = Field(min_length=2, max_length=35)
    channel: RequestChannel
    customer_tier: CustomerTier
    as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    guard_scope: GuardScopeFixture | None = None

    @model_validator(mode="after")
    def require_lane_configuration(self) -> Self:
        if self.lane == "guard_contract" and self.guard_scope is None:
            raise ValueError("Guard-contract cases require a frozen scope fixture.")
        if self.lane == "release_corpus" and self.guard_scope is not None:
            raise ValueError("Release-corpus cases cannot inject a scope fixture.")
        return self


class RetrievalBenchmarkInputSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["retrieval-v2-input-v1"]
    source: Literal["synthetic_governed_policy_corpus"]
    cases: tuple[RetrievalBenchmarkCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_cases(self) -> Self:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Frozen retrieval input IDs must be unique.")
        return self


class RetrievalBenchmarkLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^RAG2-\d{3}$")
    expected_status: EvidenceRetrievalStatus
    expected_policy_public_id: str | None = Field(
        default=None,
        pattern=r"^POL-[A-Z0-9-]+$",
        max_length=64,
    )
    expected_policy_version: int | None = Field(default=None, ge=1)
    expected_clause_public_id: str | None = Field(
        default=None,
        pattern=r"^POLC-[A-Z0-9-]+$",
        max_length=64,
    )
    near_match_clause_public_id: str | None = Field(
        default=None,
        pattern=r"^POLC-[A-Z0-9-]+$",
        max_length=64,
    )
    safety_critical: bool = False
    cross_tenant_probe: bool = False
    expected_boundary_outcome: Literal["organization_not_found"] | None = None

    @model_validator(mode="after")
    def require_relevant_answer(self) -> Self:
        expected = (
            self.expected_policy_public_id,
            self.expected_policy_version,
            self.expected_clause_public_id,
        )
        if self.expected_status is EvidenceRetrievalStatus.RELEVANT and any(
            value is None for value in expected
        ):
            raise ValueError("Relevant labels require policy, version, and clause answers.")
        if self.expected_status is not EvidenceRetrievalStatus.RELEVANT and any(
            value is not None for value in expected
        ):
            raise ValueError("Failure-state labels cannot include a relevant answer.")
        return self


class RetrievalBenchmarkLabelSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["retrieval-v2-label-v1"]
    corpus_clause_public_ids: frozenset[str] = Field(min_length=1)
    cases: tuple[RetrievalBenchmarkLabel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_and_known_answers(self) -> Self:
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Frozen retrieval label IDs must be unique.")
        unknown = sorted(
            answer
            for case in self.cases
            for answer in (
                case.expected_clause_public_id,
                case.near_match_clause_public_id,
            )
            if answer is not None and answer not in self.corpus_clause_public_ids
        )
        if unknown:
            raise ValueError(f"Retrieval labels reference unknown clauses: {unknown}.")
        return self


class RetrievalBenchmarkManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["retrieval-v2-manifest-v1"]
    inputs_file: Literal["inputs.json"]
    labels_file: Literal["labels.json"]
    inputs_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    labels_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class FrozenRetrievalBenchmark(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest: RetrievalBenchmarkManifest
    inputs: RetrievalBenchmarkInputSuite
    labels: RetrievalBenchmarkLabelSuite


def load_frozen_retrieval_benchmark(root: Path) -> FrozenRetrievalBenchmark:
    manifest = RetrievalBenchmarkManifest.model_validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    inputs_path = root / manifest.inputs_file
    labels_path = root / manifest.labels_file
    input_bytes = inputs_path.read_bytes()
    label_bytes = labels_path.read_bytes()
    _require_hash("inputs", input_bytes, manifest.inputs_sha256)
    _require_hash("labels", label_bytes, manifest.labels_sha256)
    inputs = RetrievalBenchmarkInputSuite.model_validate_json(input_bytes)
    labels = RetrievalBenchmarkLabelSuite.model_validate_json(label_bytes)
    input_ids = {case.id for case in inputs.cases}
    label_ids = {case.case_id for case in labels.cases}
    if input_ids != label_ids:
        raise ValueError(
            "Frozen retrieval coverage mismatch; "
            f"missing_labels={sorted(input_ids - label_ids)}, "
            f"extra_labels={sorted(label_ids - input_ids)}."
        )
    return FrozenRetrievalBenchmark(manifest=manifest, inputs=inputs, labels=labels)


def _require_hash(name: str, content: bytes, expected: str) -> None:
    observed = sha256(content).hexdigest()
    if observed != expected:
        raise ValueError(
            f"Frozen retrieval {name} hash mismatch; expected={expected}, observed={observed}."
        )
