from collections.abc import Iterable

from app.evaluation.public_benchmark.models import (
    BenchmarkInputRecord,
    CfpbInputRecord,
    FosInputRecord,
    UciInputRecord,
)
from app.evaluation.public_benchmark.predictions import (
    BenchmarkPredictionRecord,
    CfpbPredictionPayload,
    CfpbPredictionRecord,
    FosPredictionPayload,
    FosPredictionRecord,
    UciPredictionPayload,
    UciPredictionRecord,
)
from app.evaluation.public_benchmark.storage import canonical_json_bytes, sha256_bytes

BASELINE_NAME = "deterministic-public-baseline"
BASELINE_VERSION = "rules-v1"

_MONETARY_TERMS = (
    "refund",
    "reimburse",
    "money",
    "funds",
    "fee",
    "charge",
    "charged",
    "payment",
    "deposit",
    "withdrawal",
    "cash",
    "interest",
)
_NON_MONETARY_TERMS = (
    "correct",
    "remove",
    "delete",
    "credit report",
    "account status",
    "identity theft",
    "fraud",
    "unauthorized",
    "investigate",
    "dispute",
)
_FOS_REMEDY_ALREADY_OFFERED = (
    "compensation",
    "to apologise",
    "apologised",
    "credited",
    "removed the fee",
    "offered",
)
_FOS_CLEAR_HARM = (
    "scam",
    "fraud",
    "unauthorised",
    "unauthorized",
    "admitted",
    "error",
    "failed to",
    "didn\u2019t receive",
    "did not receive",
)
_FOS_BUSINESS_SUPPORT = (
    "in line with",
    "entitled to",
    "provided evidence",
    "account terms",
    "correctly declined",
    "reasonable",
)


def input_fingerprint(record: BenchmarkInputRecord) -> str:
    return sha256_bytes(canonical_json_bytes(record.model_dump(mode="json", exclude_none=True)))


class DeterministicPublicBaseline:
    name = BASELINE_NAME
    version = BASELINE_VERSION

    def predict(self, record: BenchmarkInputRecord) -> BenchmarkPredictionRecord:
        if isinstance(record, CfpbInputRecord):
            return self._predict_cfpb(record)
        if isinstance(record, FosInputRecord):
            return self._predict_fos(record)
        if isinstance(record, UciInputRecord):
            return self._predict_uci(record)
        raise TypeError(f"Unsupported public benchmark record: {type(record).__name__}")

    def _predict_cfpb(self, record: CfpbInputRecord) -> CfpbPredictionRecord:
        text = " ".join(
            part
            for part in (
                record.payload.product,
                record.payload.sub_product,
                record.payload.issue,
                record.payload.sub_issue,
                record.payload.narrative,
            )
            if part
        ).casefold()
        monetary = _matched_terms(text, _MONETARY_TERMS)
        non_monetary = _matched_terms(text, _NON_MONETARY_TERMS)
        if len(monetary) >= len(non_monetary) + 2:
            response = "Closed with monetary relief"
            decision_signal = "monetary-signals-dominate"
        elif non_monetary:
            response = "Closed with non-monetary relief"
            decision_signal = "correction-or-investigation-signals"
        else:
            response = "Closed with explanation"
            decision_signal = "no-specific-remedy-signal"
        return CfpbPredictionRecord(
            record_id=record.record_id,
            input_sha256=input_fingerprint(record),
            predictor=self.name,
            predictor_version=self.version,
            payload=CfpbPredictionPayload(
                company_response=response,
                timely_response=True,
                rationale_signals=[
                    decision_signal,
                    *[f"monetary:{term}" for term in monetary[:5]],
                    *[f"non-monetary:{term}" for term in non_monetary[:5]],
                ][:12],
            ),
        )

    def _predict_fos(self, record: FosInputRecord) -> FosPredictionRecord:
        text = record.payload.case_text.casefold()
        offered = _matched_terms(text, _FOS_REMEDY_ALREADY_OFFERED)
        harm = _matched_terms(text, _FOS_CLEAR_HARM)
        support = _matched_terms(text, _FOS_BUSINESS_SUPPORT)
        asks_for_more = any(
            phrase in text
            for phrase in (
                "asked for",
                "didn\u2019t reflect",
                "did not reflect",
                "not enough",
                "more compensation",
            )
        )
        if offered and asks_for_more:
            outcome = "partially_upheld"
            decision_signal = "remedy-already-offered-but-still-disputed"
        elif len(harm) > len(support):
            outcome = "upheld"
            decision_signal = "documented-harm-signals-dominate"
        else:
            outcome = "not_upheld"
            decision_signal = "insufficient-unrebutted-harm-signal"
        return FosPredictionRecord(
            record_id=record.record_id,
            input_sha256=input_fingerprint(record),
            predictor=self.name,
            predictor_version=self.version,
            payload=FosPredictionPayload(
                outcome=outcome,
                rationale_signals=[
                    decision_signal,
                    *[f"offered:{term}" for term in offered[:4]],
                    *[f"harm:{term}" for term in harm[:4]],
                    *[f"business-support:{term}" for term in support[:3]],
                ][:12],
            ),
        )

    def _predict_uci(self, record: UciInputRecord) -> UciPredictionRecord:
        sale = record.payload.sale_transaction
        cancellation = record.payload.cancellation_transaction
        checks = {
            "customer": sale.customer_ref == cancellation.customer_ref,
            "stock": sale.stock_code == cancellation.stock_code,
            "quantity": sale.quantity > 0 and sale.quantity == abs(cancellation.quantity),
            "price": sale.unit_price == cancellation.unit_price,
            "chronology": sale.invoice_at <= cancellation.invoice_at,
            "cancellation": cancellation.invoice_id.upper().startswith("C")
            and cancellation.quantity < 0,
        }
        matches = all(checks.values())
        return UciPredictionRecord(
            record_id=record.record_id,
            input_sha256=input_fingerprint(record),
            predictor=self.name,
            predictor_version=self.version,
            payload=UciPredictionPayload(
                relationship=("candidate_cancellation_match" if matches else "unrelated_pair"),
                expected_original_invoice=sale.invoice_id if matches else None,
                rationale_signals=[
                    f"{name}:{'match' if matched else 'mismatch'}"
                    for name, matched in checks.items()
                ],
            ),
        )


def _matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    return [term for term in terms if term in text]
