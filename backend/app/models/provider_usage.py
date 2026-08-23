from pydantic import BaseModel, ConfigDict, Field


class ProviderTokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    cache_write_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


ZERO_PROVIDER_TOKEN_USAGE = ProviderTokenUsage(
    input_tokens=0,
    cached_input_tokens=0,
    cache_write_input_tokens=0,
    output_tokens=0,
    reasoning_output_tokens=0,
    total_tokens=0,
)
