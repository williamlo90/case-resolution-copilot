"""Outcome and lifecycle contracts; provider acknowledgement is not business success."""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VerificationState(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"
    UNKNOWN = "unknown"
    MISMATCH = "mismatch"


def payload_digest(
    action_type: str,
    target: str,
    parameters: dict[str, str],
    impact_amount: Decimal | None = None,
    impact_currency: str | None = None,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "type": action_type,
                "target": target,
                "parameters": parameters,
                "impact_amount": str(impact_amount) if impact_amount is not None else None,
                "impact_currency": impact_currency,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class ActionReadback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation_id: str = Field(min_length=16, max_length=128)
    external_reference: str = Field(min_length=1, max_length=200)
    action_type: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=200)
    observed_parameters: dict[str, str]
    status: VerificationState
    observed_at: datetime
    effect_count: int = Field(ge=0)
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def aware(self) -> Self:
        if self.observed_at.utcoffset() is None:
            raise ValueError("Read-back timestamp must be timezone aware")
        return self


def verify_readback(
    *,
    proof: ActionReadback | None,
    operation_id: str,
    external_reference: str,
    action_type: str,
    target: str,
    parameters: dict[str, str],
    now: datetime,
    impact_amount: Decimal | None = None,
    impact_currency: str | None = None,
) -> VerificationState:
    if proof is None:
        return VerificationState.UNKNOWN
    if not now - timedelta(minutes=5) <= proof.observed_at <= now:
        return VerificationState.UNKNOWN
    if (
        proof.operation_id != operation_id
        or proof.external_reference != external_reference
        or proof.action_type != action_type
        or proof.target != target
        or proof.impact_amount != impact_amount
        or proof.impact_currency != impact_currency
        or proof.observed_parameters != parameters
        or proof.effect_count > 1
    ):
        return VerificationState.MISMATCH
    if proof.status is VerificationState.VERIFIED and proof.effect_count != 1:
        return VerificationState.MISMATCH
    return proof.status


class LifecycleConflict(RuntimeError):
    pass
