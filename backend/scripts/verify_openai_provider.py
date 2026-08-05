import json
from typing import Any, Literal, cast

from openai import APIStatusError, APITimeoutError, OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict

from app.config import Settings


class ProviderProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


def main() -> int:
    settings = Settings()
    api_key = settings.openai_secret()
    if settings.model_provider != "openai" or not api_key:
        print(
            json.dumps(
                {
                    "status": "not_configured",
                    "provider": settings.model_provider,
                }
            )
        )
        return 2

    try:
        with OpenAI(
            api_key=api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        ) as client:
            response = client.responses.parse(
                model=cast(Any, settings.openai_model),
                instructions="Return the requested structured health result only.",
                input="Confirm that this model request is available by returning status ok.",
                text_format=ProviderProbe,
                reasoning={"effort": "low"},
                max_output_tokens=256,
                store=False,
            )
    except APITimeoutError:
        print(
            json.dumps(
                {
                    "status": "timeout",
                    "provider": "openai",
                    "model": settings.openai_model,
                }
            )
        )
        return 3
    except APIStatusError as exc:
        error_text = str(exc).lower()
        unsupported_fields = [
            field
            for field in (
                "reasoning",
                "verbosity",
                "max_output_tokens",
                "store",
                "text_format",
                "response_format",
                "instructions",
            )
            if field in error_text
        ]
        print(
            json.dumps(
                {
                    "status": "api_error",
                    "provider": "openai",
                    "model": settings.openai_model,
                    "http_status": exc.status_code,
                    "error_code": getattr(exc, "code", None),
                    "error_param": getattr(exc, "param", None),
                    "unsupported_fields": unsupported_fields,
                }
            )
        )
        return 4
    except OpenAIError:
        print(
            json.dumps(
                {
                    "status": "connection_error",
                    "provider": "openai",
                    "model": settings.openai_model,
                }
            )
        )
        return 5

    if response.output_parsed is None or response.output_parsed.status != "ok":
        print(
            json.dumps(
                {
                    "status": "invalid_response",
                    "provider": "openai",
                    "model": settings.openai_model,
                }
            )
        )
        return 6

    print(
        json.dumps(
            {
                "status": "ok",
                "provider": "openai",
                "model": settings.openai_model,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
