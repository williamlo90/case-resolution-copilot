from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.provider_usage import (
    ZERO_PROVIDER_TOKEN_USAGE,
    ProviderTokenUsage,
)

TOKENS_PER_MILLION = Decimal("1000000")


class ProviderTokenPricing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1, max_length=100)
    checked_on: date
    source_url: str = Field(min_length=1, max_length=500)
    input_usd_per_million: float = Field(ge=0)
    cached_input_usd_per_million: float = Field(ge=0)
    cache_write_input_usd_per_million: float = Field(ge=0)
    output_usd_per_million: float = Field(ge=0)


class ProviderCostSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_calls: int = Field(ge=0)
    usage_records: int = Field(ge=0)
    usage_complete: bool
    token_usage: ProviderTokenUsage
    pricing: ProviderTokenPricing | None
    total_cost_usd: float | None = Field(default=None, ge=0)
    cost_per_evaluated_case_usd: float | None = Field(default=None, ge=0)
    cost_per_provider_call_usd: float | None = Field(default=None, ge=0)


def summarize_provider_cost(
    *,
    usage_records: tuple[ProviderTokenUsage, ...],
    provider_calls: int,
    evaluated_cases: int,
    pricing: ProviderTokenPricing | None,
) -> ProviderCostSummary:
    usage = aggregate_provider_usage(usage_records)
    usage_complete = len(usage_records) == provider_calls
    total_cost = (
        price_provider_usage(usage, pricing) if pricing is not None and usage_complete else None
    )
    return ProviderCostSummary(
        provider_calls=provider_calls,
        usage_records=len(usage_records),
        usage_complete=usage_complete,
        token_usage=usage,
        pricing=pricing,
        total_cost_usd=total_cost,
        cost_per_evaluated_case_usd=(
            _rounded_cost(Decimal(str(total_cost)) / evaluated_cases)
            if total_cost is not None and evaluated_cases > 0
            else None
        ),
        cost_per_provider_call_usd=(
            _rounded_cost(Decimal(str(total_cost)) / provider_calls)
            if total_cost is not None and provider_calls > 0
            else None
        ),
    )


def aggregate_provider_usage(
    records: tuple[ProviderTokenUsage, ...],
) -> ProviderTokenUsage:
    if not records:
        return ZERO_PROVIDER_TOKEN_USAGE
    return ProviderTokenUsage(
        input_tokens=sum(item.input_tokens for item in records),
        cached_input_tokens=sum(item.cached_input_tokens for item in records),
        cache_write_input_tokens=sum(item.cache_write_input_tokens for item in records),
        output_tokens=sum(item.output_tokens for item in records),
        reasoning_output_tokens=sum(item.reasoning_output_tokens for item in records),
        total_tokens=sum(item.total_tokens for item in records),
    )


def price_provider_usage(
    usage: ProviderTokenUsage,
    pricing: ProviderTokenPricing,
) -> float:
    discounted_input = usage.cached_input_tokens + usage.cache_write_input_tokens
    if discounted_input > usage.input_tokens:
        raise ValueError("Detailed input-token usage exceeds total input tokens.")
    regular_input = usage.input_tokens - discounted_input
    cost = (
        Decimal(regular_input) * Decimal(str(pricing.input_usd_per_million))
        + Decimal(usage.cached_input_tokens) * Decimal(str(pricing.cached_input_usd_per_million))
        + Decimal(usage.cache_write_input_tokens)
        * Decimal(str(pricing.cache_write_input_usd_per_million))
        + Decimal(usage.output_tokens) * Decimal(str(pricing.output_usd_per_million))
    ) / TOKENS_PER_MILLION
    return _rounded_cost(cost)


def _rounded_cost(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000000000001")))
