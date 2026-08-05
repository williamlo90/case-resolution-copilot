from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

SuiteName = Literal["cfpb", "fos", "uci"]
FosOutcome = Literal["upheld", "partially_upheld", "not_upheld"]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
RecordId = Annotated[
    str,
    StringConstraints(pattern=r"^(?:cfpb|fos|uci)-[A-Za-z0-9][A-Za-z0-9-]*$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRecord(StrictModel):
    schema_version: Literal["public-benchmark-record-v1"] = "public-benchmark-record-v1"
    suite: SuiteName
    record_id: RecordId
    source_record_id: str = Field(min_length=1, max_length=200)
    source_url: str
    retrieved_at: datetime
    source_artifact_sha256: Sha256

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("Public benchmark sources must use HTTPS.")
        return value


class CfpbInputPayload(StrictModel):
    received_on: date
    product: str = Field(min_length=1)
    sub_product: str | None = None
    issue: str = Field(min_length=1)
    sub_issue: str | None = None
    submitted_via: str = Field(min_length=1)
    narrative: str = Field(min_length=20)


class CfpbLabelPayload(StrictModel):
    company_response: str = Field(min_length=1)
    timely_response: bool


class CfpbInputRecord(SourceRecord):
    suite: Literal["cfpb"] = "cfpb"
    payload: CfpbInputPayload


class CfpbLabelRecord(SourceRecord):
    suite: Literal["cfpb"] = "cfpb"
    payload: CfpbLabelPayload


class FosInputPayload(StrictModel):
    case_text: str = Field(min_length=200)
    removed_outcome_fragments: int = Field(ge=0)


class FosLabelPayload(StrictModel):
    outcome: FosOutcome
    final_decision_text: str = Field(min_length=20)


class FosInputRecord(SourceRecord):
    suite: Literal["fos"] = "fos"
    payload: FosInputPayload


class FosLabelRecord(SourceRecord):
    suite: Literal["fos"] = "fos"
    payload: FosLabelPayload


class UciTransaction(StrictModel):
    invoice_id: str = Field(min_length=1)
    stock_code: str = Field(min_length=1)
    description: str | None = None
    quantity: int
    invoice_at: datetime
    unit_price: str = Field(pattern=r"^-?\d+(?:\.\d+)?$")
    customer_ref: str = Field(pattern=r"^customer-[a-f0-9]{12}$")
    country: str = Field(min_length=1)


class UciInputPayload(StrictModel):
    sale_transaction: UciTransaction
    cancellation_transaction: UciTransaction


class UciLabelPayload(StrictModel):
    relationship: Literal["candidate_cancellation_match", "unrelated_pair"]
    label_basis: Literal["derived_exact_match_rule", "constructed_negative"]
    expected_original_invoice: str | None = None

    @model_validator(mode="after")
    def require_expected_invoice_for_match(self) -> "UciLabelPayload":
        if self.relationship == "candidate_cancellation_match":
            if not self.expected_original_invoice:
                raise ValueError("Matched UCI pairs require the expected original invoice.")
            if self.label_basis != "derived_exact_match_rule":
                raise ValueError("Matched UCI pairs must use the exact-match label basis.")
        elif self.expected_original_invoice is not None:
            raise ValueError("Unrelated UCI pairs cannot name an expected original invoice.")
        return self


class UciInputRecord(SourceRecord):
    suite: Literal["uci"] = "uci"
    payload: UciInputPayload


class UciLabelRecord(SourceRecord):
    suite: Literal["uci"] = "uci"
    payload: UciLabelPayload


BenchmarkInputRecord = Annotated[
    CfpbInputRecord | FosInputRecord | UciInputRecord,
    Field(discriminator="suite"),
]
BenchmarkLabelRecord = Annotated[
    CfpbLabelRecord | FosLabelRecord | UciLabelRecord,
    Field(discriminator="suite"),
]

BENCHMARK_INPUT_ADAPTER: TypeAdapter[BenchmarkInputRecord] = TypeAdapter(BenchmarkInputRecord)
BENCHMARK_LABEL_ADAPTER: TypeAdapter[BenchmarkLabelRecord] = TypeAdapter(BenchmarkLabelRecord)


class CfpbSourceConfig(StrictModel):
    api_url: str
    dataset_url: str
    license: Literal["CC0"]
    date_received_min: date
    date_received_max: date
    response_labels: list[str] = Field(min_length=2, max_length=5)
    records_per_label: int = Field(ge=1, le=25)

    @model_validator(mode="after")
    def validate_dates_and_labels(self) -> "CfpbSourceConfig":
        if self.date_received_max <= self.date_received_min:
            raise ValueError("CFPB maximum date must be later than its minimum date.")
        if len(set(self.response_labels)) != len(self.response_labels):
            raise ValueError("CFPB response labels must be unique.")
        return self


class FosCaseConfig(StrictModel):
    decision_id: str = Field(pattern=r"^DRN-\d{7}$")
    expected_outcome: FosOutcome
    source_url: str

    @model_validator(mode="after")
    def validate_source_url(self) -> "FosCaseConfig":
        if self.decision_id not in self.source_url:
            raise ValueError("FOS source URL must contain its decision ID.")
        return self


class FosSourceConfig(StrictModel):
    dataset_url: str
    license: str = Field(min_length=1)
    cases: list[FosCaseConfig] = Field(min_length=4, max_length=12)

    @model_validator(mode="after")
    def validate_case_balance(self) -> "FosSourceConfig":
        ids = [case.decision_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("FOS decision IDs must be unique.")
        outcomes = {case.expected_outcome for case in self.cases}
        if "not_upheld" not in outcomes or outcomes.isdisjoint({"upheld", "partially_upheld"}):
            raise ValueError("FOS cases must contain upheld and not-upheld outcomes.")
        return self


class UciSourceConfig(StrictModel):
    dataset_url: str
    download_url: str
    doi: str = Field(pattern=r"^10\.\d{4,9}/\S+$")
    license: Literal["CC BY 4.0"]
    max_rows_per_sheet: int = Field(ge=1000, le=30000)
    positive_pairs: int = Field(ge=5, le=30)


class PublicBenchmarkSources(StrictModel):
    schema_version: Literal["public-benchmark-sources-v1"]
    cfpb: CfpbSourceConfig
    fos: FosSourceConfig
    uci: UciSourceConfig


class ArtifactManifest(StrictModel):
    suite: SuiteName
    kind: Literal["raw", "prepared_input", "prepared_label"]
    path: str = Field(min_length=1)
    sha256: Sha256
    bytes: int = Field(ge=0)
    records: int | None = Field(default=None, ge=0)

    @field_validator("path")
    @classmethod
    def require_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            raise ValueError("Manifest artifact paths must be safe relative paths.")
        return normalized


class SourceSnapshot(StrictModel):
    suite: SuiteName
    name: str = Field(min_length=1)
    canonical_url: str
    license: str = Field(min_length=1)
    retrieved_at: datetime
    details: dict[str, str | int | bool | list[str]]


class ValidationSummary(StrictModel):
    passed: bool
    input_records: dict[SuiteName, int]
    label_records: dict[SuiteName, int]
    checks: list[str] = Field(min_length=1)


class PublicBenchmarkManifest(StrictModel):
    schema_version: Literal["public-benchmark-manifest-v1"] = "public-benchmark-manifest-v1"
    generator: Literal["public-benchmark-setup-v1"] = "public-benchmark-setup-v1"
    generated_at: datetime
    config_sha256: Sha256
    sources: list[SourceSnapshot] = Field(min_length=3, max_length=3)
    artifacts: list[ArtifactManifest] = Field(min_length=6)
    validation: ValidationSummary
