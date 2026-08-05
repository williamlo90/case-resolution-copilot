from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.evaluation.public_benchmark.models import FosCaseConfig
from app.evaluation.public_benchmark.storage import write_jsonl
from app.evaluation.public_benchmark.transforms import (
    UciRow,
    build_uci_pairs,
    transform_cfpb_hit,
    transform_fos_decision,
)
from app.evaluation.public_benchmark.validation import validate_public_benchmark
from app.evaluation.public_benchmark.xlsx_stream import iter_xlsx_rows

HASH = "a" * 64
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def test_cfpb_response_fields_are_kept_out_of_model_input() -> None:
    input_record, label_record = transform_cfpb_hit(
        {
            "_source": {
                "complaint_id": "12345",
                "date_received": "2025-01-02T00:00:00.000Z",
                "product": "Money transfer",
                "sub_product": "Mobile transfer",
                "issue": "Funds were not received",
                "sub_issue": None,
                "submitted_via": "Web",
                "complaint_what_happened": (
                    "The transfer was marked complete, but the recipient did not receive it."
                ),
                "company_response": "Closed with monetary relief",
                "timely": "Yes",
            }
        },
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
        api_url="https://example.test/api/",
    )

    serialized_input = input_record.model_dump(mode="json")
    assert "company_response" not in str(serialized_input)
    assert "timely_response" not in str(serialized_input)
    assert label_record.payload.company_response == "Closed with monetary relief"
    assert label_record.payload.timely_response is True


def test_fos_transform_removes_outcome_paragraphs_before_reasoning() -> None:
    repeated_facts = (
        "The customer supplied account records, correspondence, dates, and transaction details. "
        * 5
    )
    text = f"""
    Decision Reference DRN-1234567

    The complaint

    Mrs A complains that the business handled her disputed payment unfairly.

    What happened

    {repeated_facts}

    Our investigator upheld the complaint and proposed compensation.

    The investigator recommended a refund after reviewing the account records.

    What I've decided - and why

    I reviewed the evidence and the applicable account terms.

    My final decision

    My final decision is that I uphold this complaint against Example Bank Plc.

    Under the rules of the Financial Ombudsman Service, I am required to ask Mrs A to respond.
    """
    case = FosCaseConfig(
        decision_id="DRN-1234567",
        expected_outcome="upheld",
        source_url="https://example.test/decision/DRN-1234567.pdf",
    )

    input_record, label_record = transform_fos_decision(
        text,
        case,
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
    )

    assert input_record.payload.removed_outcome_fragments == 2
    assert "uphold" not in input_record.payload.case_text.casefold()
    assert label_record.payload.outcome == "upheld"
    assert "uphold this complaint" in label_record.payload.final_decision_text.casefold()


def test_fos_transform_fails_closed_when_configured_outcome_is_wrong() -> None:
    text = """
    Decision Reference DRN-1234567

    The complaint

    The customer disputes a payment after supplying a detailed account chronology and records.

    What happened

    The parties exchanged evidence over several months. The file contains enough factual
    background to exceed the minimum blind input size without disclosing the eventual answer.
    The business reviewed the account, the transaction history, and its correspondence records.

    What I've decided - and why

    I considered the available evidence.

    My final decision

    I do not uphold this complaint.

    Under the rules of the Financial Ombudsman Service, the customer may respond.
    """
    case = FosCaseConfig(
        decision_id="DRN-1234567",
        expected_outcome="upheld",
        source_url="https://example.test/decision/DRN-1234567.pdf",
    )

    with pytest.raises(ValueError, match="expected upheld, detected not_upheld"):
        transform_fos_decision(
            text,
            case,
            retrieved_at=NOW,
            source_artifact_sha256=HASH,
        )


def test_uci_pair_builder_is_balanced_and_deterministic() -> None:
    rows = _uci_rows()
    first_inputs, first_labels = build_uci_pairs(
        rows,
        positive_pair_limit=2,
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
        source_url="https://example.test/uci",
    )
    second_inputs, second_labels = build_uci_pairs(
        list(reversed(rows)),
        positive_pair_limit=2,
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
        source_url="https://example.test/uci",
    )

    assert [record.model_dump(mode="json") for record in first_inputs] == [
        record.model_dump(mode="json") for record in second_inputs
    ]
    assert [record.model_dump(mode="json") for record in first_labels] == [
        record.model_dump(mode="json") for record in second_labels
    ]
    relationships = [record.payload.relationship for record in first_labels]
    assert relationships.count("candidate_cancellation_match") == 2
    assert relationships.count("unrelated_pair") == 2
    assert all(
        not record.payload.sale_transaction.customer_ref.endswith("10001")
        for record in first_inputs
    )


def test_streaming_xlsx_reader_handles_shared_strings(tmp_path: Path) -> None:
    workbook = tmp_path / "sample.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Year 1" sheetId="1" r:id="rId1"/></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
                Target="worksheets/sheet1.xml"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <si><t>Invoice</t></si><si><t>StockCode</t></si>
              <si><t>489434</t></si><si><t>85048</t></si>
            </sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
                <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>
              </sheetData>
            </worksheet>""",
        )

    rows = list(iter_xlsx_rows(workbook, max_rows_per_sheet=10))

    assert rows == [("Year 1", {"Invoice": "489434", "StockCode": "85048"})]


def test_validator_accepts_separate_aligned_suites(tmp_path: Path) -> None:
    cfpb_input, cfpb_label = transform_cfpb_hit(
        {
            "_source": {
                "complaint_id": "98765",
                "date_received": "2025-02-01",
                "product": "Checking account",
                "sub_product": None,
                "issue": "Cash withdrawal",
                "sub_issue": None,
                "submitted_via": "Web",
                "complaint_what_happened": (
                    "A cash withdrawal appeared twice and the correction was still pending."
                ),
                "company_response": "Closed with explanation",
                "timely": "No",
            }
        },
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
        api_url="https://example.test/api",
    )
    fos_input, fos_label = transform_fos_decision(
        """
        Decision Reference DRN-1234567

        The complaint

        The customer says the business handled a disputed account transaction unfairly.

        What happened

        The customer supplied correspondence, a transaction history, account statements, and a
        detailed chronology. The business supplied its own records and account terms. Both sides
        confirmed the relevant dates and the amount in dispute, providing enough factual context
        for a blind review without revealing the adjudicator's eventual conclusion.

        What I've decided - and why

        I considered the evidence.

        My final decision

        I uphold this complaint.

        Under the rules of the Financial Ombudsman Service, the customer may respond.
        """,
        FosCaseConfig(
            decision_id="DRN-1234567",
            expected_outcome="upheld",
            source_url="https://example.test/decision/DRN-1234567.pdf",
        ),
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
    )
    uci_inputs, uci_labels = build_uci_pairs(
        _uci_rows(),
        positive_pair_limit=2,
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
        source_url="https://example.test/uci",
    )

    prepared = tmp_path / "prepared"
    for suite, inputs, labels in (
        ("cfpb", [cfpb_input], [cfpb_label]),
        ("fos", [fos_input], [fos_label]),
        ("uci", uci_inputs, uci_labels),
    ):
        write_jsonl(tmp_path, prepared / suite / "inputs.jsonl", inputs)
        write_jsonl(tmp_path, prepared / suite / "labels.jsonl", labels)

    summary = validate_public_benchmark(tmp_path, require_manifest=False)

    assert summary.passed is True
    assert summary.input_records == {"cfpb": 1, "fos": 1, "uci": 4}
    assert summary.label_records == {"cfpb": 1, "fos": 1, "uci": 4}

    tampered_fos_input = fos_input.model_copy(
        update={
            "payload": fos_input.payload.model_copy(
                update={
                    "case_text": (
                        f"{fos_input.payload.case_text} "
                        "The investigator recommended that the complaint succeed."
                    )
                }
            )
        }
    )
    write_jsonl(
        tmp_path,
        prepared / "fos" / "inputs.jsonl",
        [tampered_fos_input],
    )
    with pytest.raises(ValueError, match="FOS outcome leakage"):
        validate_public_benchmark(tmp_path, require_manifest=False)


def _uci_rows() -> list[UciRow]:
    return [
        UciRow(
            invoice_id="100001",
            stock_code="SKU-A",
            description="Item A",
            quantity=2,
            invoice_at=NOW,
            unit_price=Decimal("10.00"),
            customer_id="10001",
            country="United Kingdom",
        ),
        UciRow(
            invoice_id="100002",
            stock_code="SKU-B",
            description="Item B",
            quantity=1,
            invoice_at=NOW + timedelta(minutes=1),
            unit_price=Decimal("12.50"),
            customer_id="10002",
            country="United Kingdom",
        ),
        UciRow(
            invoice_id="C100003",
            stock_code="SKU-A",
            description="Item A",
            quantity=-2,
            invoice_at=NOW + timedelta(days=1),
            unit_price=Decimal("10.00"),
            customer_id="10001",
            country="United Kingdom",
        ),
        UciRow(
            invoice_id="C100004",
            stock_code="SKU-B",
            description="Item B",
            quantity=-1,
            invoice_at=NOW + timedelta(days=1, minutes=1),
            unit_price=Decimal("12.50"),
            customer_id="10002",
            country="United Kingdom",
        ),
    ]
