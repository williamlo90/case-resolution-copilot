from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


UtcDateTime = Annotated[datetime, AfterValidator(_require_utc)]
Version = Annotated[int, Field(ge=1)]
PublicId = Annotated[str, Field(min_length=1, max_length=64)]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
MoneyAmount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MoneyResponse(ApiSchema):
    amount: MoneyAmount
    currency: CurrencyCode


class ActorSummaryResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=200)


class SourceFreshnessResponse(ApiSchema):
    status: Literal["current", "stale", "unavailable"]
    checked_at: UtcDateTime | None


class ResponseMeta(ApiSchema):
    data_mode: Literal["demo", "connected", "degraded"] = "demo"
    contract_version: Literal["2026-07-22"] = "2026-07-22"


class DataResponse[ItemT](ApiSchema):
    data: ItemT
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class CursorPage[ItemT](ApiSchema):
    items: list[ItemT]
    next_cursor: str | None
    total: int = Field(ge=0)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
