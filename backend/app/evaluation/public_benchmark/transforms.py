import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from app.evaluation.public_benchmark.models import (
    CfpbInputPayload,
    CfpbInputRecord,
    CfpbLabelPayload,
    CfpbLabelRecord,
    FosCaseConfig,
    FosInputPayload,
    FosInputRecord,
    FosLabelPayload,
    FosLabelRecord,
    FosOutcome,
    UciInputPayload,
    UciInputRecord,
    UciLabelPayload,
    UciLabelRecord,
    UciTransaction,
)

_FOS_REASONING_HEADINGS = (
    re.compile(r"\bwhat i(?:'|’|‘)ve decided\s*(?:-|–|—)?\s*and why\b", re.IGNORECASE),
    re.compile(r"\bwhat i think\b", re.IGNORECASE),
    re.compile(r"\bmy findings\b", re.IGNORECASE),
)
_FOS_OUTCOME_LEAKAGE = (
    re.compile(r"\b(?:uphold(?:s|ing|ed)?|upheld)\b", re.IGNORECASE),
    re.compile(r"\binvestigator(?:'s|’s)?\b", re.IGNORECASE),
    re.compile(r"\brecommend(?:s|ed|ing|ation|ations)?\b", re.IGNORECASE),
    re.compile(r"\bprovisional decision\b", re.IGNORECASE),
    re.compile(r"\bfinal decision\b", re.IGNORECASE),
)
_FOS_FINAL_HEADING = re.compile(r"\bmy final decision\b", re.IGNORECASE)
_FOS_RULES_FOOTER = re.compile(r"\bunder the rules of the financial ombudsman", re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n+", normalized):
        compact = re.sub(r"[ \t\n]+", " ", paragraph).strip()
        if compact:
            paragraphs.append(compact)
    return "\n\n".join(paragraphs)


def transform_cfpb_hit(
    hit: dict[str, Any],
    *,
    retrieved_at: datetime,
    source_artifact_sha256: str,
    api_url: str,
) -> tuple[CfpbInputRecord, CfpbLabelRecord]:
    source = hit.get("_source")
    if not isinstance(source, dict):
        raise ValueError("CFPB API hit is missing its _source object.")

    complaint_id = _required_string(source, "complaint_id")
    narrative = normalize_text(_required_string(source, "complaint_what_happened"))
    timely = _required_string(source, "timely")
    if timely not in {"Yes", "No"}:
        raise ValueError(f"Unsupported CFPB timely response value: {timely}")

    source_url = f"{api_url.rstrip('/')}/{complaint_id}"
    common = {
        "record_id": f"cfpb-{complaint_id}",
        "source_record_id": complaint_id,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "source_artifact_sha256": source_artifact_sha256,
    }
    input_record = CfpbInputRecord(
        **common,
        payload=CfpbInputPayload(
            received_on=_parse_cfpb_date(_required_string(source, "date_received")),
            product=_required_string(source, "product"),
            sub_product=_optional_string(source.get("sub_product")),
            issue=_required_string(source, "issue"),
            sub_issue=_optional_string(source.get("sub_issue")),
            submitted_via=_required_string(source, "submitted_via"),
            narrative=narrative,
        ),
    )
    label_record = CfpbLabelRecord(
        **common,
        payload=CfpbLabelPayload(
            company_response=_required_string(source, "company_response"),
            timely_response=timely == "Yes",
        ),
    )
    return input_record, label_record


def transform_fos_decision(
    text: str,
    case: FosCaseConfig,
    *,
    retrieved_at: datetime,
    source_artifact_sha256: str,
) -> tuple[FosInputRecord, FosLabelRecord]:
    normalized = normalize_text(text)
    if case.decision_id not in normalized:
        raise ValueError(f"Extracted FOS text does not contain {case.decision_id}.")

    reasoning_start = _find_first_heading(normalized, _FOS_REASONING_HEADINGS)
    if reasoning_start is None:
        raise ValueError(f"{case.decision_id} has no supported reasoning heading.")

    complaint_start_match = re.search(
        r"\bthe complaint(?:\s+and what happened)?\b",
        normalized,
        re.IGNORECASE,
    )
    complaint_start = complaint_start_match.start() if complaint_start_match else 0
    if complaint_start >= reasoning_start:
        raise ValueError(f"{case.decision_id} has an invalid complaint/reasoning order.")

    candidate_input = normalized[complaint_start:reasoning_start].strip()
    clean_paragraphs: list[str] = []
    removed = 0
    for paragraph in candidate_input.split("\n\n"):
        clean_fragments: list[str] = []
        for fragment in re.split(r"(?<=[.!?])\s+", paragraph):
            if any(pattern.search(fragment) for pattern in _FOS_OUTCOME_LEAKAGE):
                removed += 1
                continue
            clean_fragments.append(fragment)
        if clean_fragments:
            clean_paragraphs.append(" ".join(clean_fragments))
    case_text = "\n\n".join(clean_paragraphs).strip()
    if len(case_text) < 200:
        raise ValueError(f"{case.decision_id} has too little blind input after leakage removal.")
    if find_fos_outcome_leakage(case_text):
        raise ValueError(f"{case.decision_id} still contains outcome leakage.")

    final_text = _extract_final_decision(normalized, case.decision_id)
    detected_outcome = classify_fos_outcome(final_text)
    if detected_outcome != case.expected_outcome:
        raise ValueError(
            f"{case.decision_id} expected {case.expected_outcome}, detected {detected_outcome}."
        )

    common = {
        "record_id": f"fos-{case.decision_id.lower()}",
        "source_record_id": case.decision_id,
        "source_url": case.source_url,
        "retrieved_at": retrieved_at,
        "source_artifact_sha256": source_artifact_sha256,
    }
    return (
        FosInputRecord(
            **common,
            payload=FosInputPayload(
                case_text=case_text,
                removed_outcome_fragments=removed,
            ),
        ),
        FosLabelRecord(
            **common,
            payload=FosLabelPayload(
                outcome=detected_outcome,
                final_decision_text=final_text,
            ),
        ),
    )


def find_fos_outcome_leakage(text: str) -> list[str]:
    return [pattern.pattern for pattern in _FOS_OUTCOME_LEAKAGE if pattern.search(text)]


def classify_fos_outcome(final_decision_text: str) -> FosOutcome:
    lowered = final_decision_text.casefold().replace("’", "'").replace("‘", "'")
    if re.search(r"\buphold\b.{0,60}\b(?:in part|to the extent)\b", lowered):
        return "partially_upheld"
    if re.search(r"\b(?:do not|don't|did not|didn't)\s+uphold\b", lowered):
        return "not_upheld"
    if re.search(r"\buphold\b", lowered):
        return "upheld"
    raise ValueError("Could not classify the FOS final decision outcome.")


@dataclass(frozen=True)
class UciRow:
    invoice_id: str
    stock_code: str
    description: str | None
    quantity: int
    invoice_at: datetime
    unit_price: Decimal
    customer_id: str
    country: str

    @property
    def is_cancellation(self) -> bool:
        return self.invoice_id.upper().startswith("C") and self.quantity < 0

    @property
    def exact_match_key(self) -> tuple[str, str, int, Decimal]:
        return (
            self.customer_id,
            self.stock_code,
            abs(self.quantity),
            self.unit_price,
        )


def uci_row_from_mapping(row: dict[str, str | None]) -> UciRow | None:
    normalized = {_normalize_column_name(key): value for key, value in row.items()}
    invoice_id = _clean_excel_identifier(normalized.get("invoice") or normalized.get("invoiceno"))
    stock_code = _clean_excel_identifier(normalized.get("stockcode"))
    customer_id = _clean_excel_identifier(
        normalized.get("customerid") or normalized.get("customer")
    )
    country = _optional_string(normalized.get("country"))
    quantity_raw = normalized.get("quantity")
    price_raw = normalized.get("price") or normalized.get("unitprice")
    date_raw = normalized.get("invoicedate")
    if not all((invoice_id, stock_code, customer_id, country, quantity_raw, price_raw, date_raw)):
        return None
    assert country is not None
    try:
        quantity = int(Decimal(str(quantity_raw)))
        unit_price = Decimal(str(price_raw)).normalize()
        invoice_at = _parse_uci_datetime(str(date_raw))
    except (InvalidOperation, ValueError):
        return None
    if quantity == 0 or unit_price < 0:
        return None
    return UciRow(
        invoice_id=invoice_id,
        stock_code=stock_code,
        description=_optional_string(normalized.get("description")),
        quantity=quantity,
        invoice_at=invoice_at,
        unit_price=unit_price,
        customer_id=customer_id,
        country=country,
    )


def build_uci_pairs(
    rows: list[UciRow],
    *,
    positive_pair_limit: int,
    retrieved_at: datetime,
    source_artifact_sha256: str,
    source_url: str,
) -> tuple[list[UciInputRecord], list[UciLabelRecord]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.invoice_at,
            row.invoice_id,
            row.stock_code,
            row.quantity,
        ),
    )
    sales_by_key: dict[tuple[str, str, int, Decimal], list[UciRow]] = {}
    positive_pairs: list[tuple[UciRow, UciRow]] = []
    used_sales: set[tuple[str, str, datetime, int]] = set()

    for row in ordered:
        if row.is_cancellation:
            candidates = sales_by_key.get(row.exact_match_key, [])
            sale = next(
                (
                    candidate
                    for candidate in reversed(candidates)
                    if candidate.invoice_at <= row.invoice_at
                    and _uci_row_identity(candidate) not in used_sales
                ),
                None,
            )
            if sale is not None:
                positive_pairs.append((sale, row))
                used_sales.add(_uci_row_identity(sale))
                if len(positive_pairs) >= positive_pair_limit:
                    break
        elif row.quantity > 0:
            sales_by_key.setdefault(row.exact_match_key, []).append(row)

    if len(positive_pairs) < positive_pair_limit:
        raise ValueError(
            f"UCI bounded scan found {len(positive_pairs)} exact pairs; "
            f"{positive_pair_limit} required."
        )

    input_records: list[UciInputRecord] = []
    label_records: list[UciLabelRecord] = []
    for index, (sale, cancellation) in enumerate(positive_pairs, start=1):
        positive_input, positive_label = _make_uci_record_pair(
            index=index,
            suffix="match",
            sale=sale,
            cancellation=cancellation,
            relationship="candidate_cancellation_match",
            retrieved_at=retrieved_at,
            source_artifact_sha256=source_artifact_sha256,
            source_url=source_url,
        )
        input_records.append(positive_input)
        label_records.append(positive_label)

        unrelated_sale = _find_unrelated_sale(positive_pairs, index - 1, cancellation)
        negative_input, negative_label = _make_uci_record_pair(
            index=index,
            suffix="unrelated",
            sale=unrelated_sale,
            cancellation=cancellation,
            relationship="unrelated_pair",
            retrieved_at=retrieved_at,
            source_artifact_sha256=source_artifact_sha256,
            source_url=source_url,
        )
        input_records.append(negative_input)
        label_records.append(negative_label)
    return input_records, label_records


def _make_uci_record_pair(
    *,
    index: int,
    suffix: Literal["match", "unrelated"],
    sale: UciRow,
    cancellation: UciRow,
    relationship: Literal["candidate_cancellation_match", "unrelated_pair"],
    retrieved_at: datetime,
    source_artifact_sha256: str,
    source_url: str,
) -> tuple[UciInputRecord, UciLabelRecord]:
    record_id = f"uci-pair-{index:03d}-{suffix}"
    source_record_id = f"{sale.invoice_id}::{cancellation.invoice_id}::{sale.stock_code}"
    common = {
        "record_id": record_id,
        "source_record_id": source_record_id,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "source_artifact_sha256": source_artifact_sha256,
    }
    input_record = UciInputRecord(
        **common,
        payload=UciInputPayload(
            sale_transaction=_uci_transaction(sale),
            cancellation_transaction=_uci_transaction(cancellation),
        ),
    )
    label_record = UciLabelRecord(
        **common,
        payload=UciLabelPayload(
            relationship=relationship,
            label_basis=(
                "derived_exact_match_rule"
                if relationship == "candidate_cancellation_match"
                else "constructed_negative"
            ),
            expected_original_invoice=(
                sale.invoice_id if relationship == "candidate_cancellation_match" else None
            ),
        ),
    )
    return input_record, label_record


def _find_unrelated_sale(
    pairs: list[tuple[UciRow, UciRow]],
    current_index: int,
    cancellation: UciRow,
) -> UciRow:
    for offset in range(1, len(pairs)):
        candidate = pairs[(current_index + offset) % len(pairs)][0]
        if candidate.exact_match_key != cancellation.exact_match_key:
            return candidate
    raise ValueError("Could not construct an unrelated UCI transaction pair.")


def _uci_transaction(row: UciRow) -> UciTransaction:
    return UciTransaction(
        invoice_id=row.invoice_id,
        stock_code=row.stock_code,
        description=row.description,
        quantity=row.quantity,
        invoice_at=row.invoice_at,
        unit_price=format(row.unit_price, "f"),
        customer_ref=f"customer-{hashlib.sha256(f'uci-v1:{row.customer_id}'.encode()).hexdigest()[:12]}",
        country=row.country,
    )


def _uci_row_identity(row: UciRow) -> tuple[str, str, datetime, int]:
    return row.invoice_id, row.stock_code, row.invoice_at, row.quantity


def _extract_final_decision(text: str, decision_id: str) -> str:
    matches = list(_FOS_FINAL_HEADING.finditer(text))
    if not matches:
        raise ValueError(f"{decision_id} has no final-decision heading.")
    start = matches[-1].end()
    footer = _FOS_RULES_FOOTER.search(text, start)
    end = footer.start() if footer else len(text)
    final_text = text[start:end].strip()
    final_text = re.sub(r"\n{3,}", "\n\n", final_text)
    if len(final_text) < 20:
        raise ValueError(f"{decision_id} has an empty final-decision section.")
    return final_text


def _find_first_heading(text: str, patterns: tuple[re.Pattern[str], ...]) -> int | None:
    starts = [match.start() for pattern in patterns if (match := pattern.search(text))]
    return min(starts) if starts else None


def _required_string(source: dict[str, Any], key: str) -> str:
    value = _optional_string(source.get(key))
    if value is None:
        raise ValueError(f"Required source field is missing: {key}")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_cfpb_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _normalize_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _clean_excel_identifier(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.strip()
    if re.fullmatch(r"-?\d+\.0+", normalized):
        return normalized.split(".", maxsplit=1)[0]
    return normalized


def _parse_uci_datetime(value: str) -> datetime:
    stripped = value.strip()
    try:
        serial = Decimal(stripped)
    except InvalidOperation:
        serial = None
    if serial is not None:
        return datetime(1899, 12, 30) + timedelta(days=float(serial))
    for pattern in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(stripped, pattern)
        except ValueError:
            continue
    raise ValueError(f"Unsupported UCI invoice date: {value}")
