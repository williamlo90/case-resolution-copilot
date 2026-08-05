from collections.abc import Mapping
from typing import Any

SENSITIVE_FIELDS = frozenset(
    {
        "contact",
        "customer_message",
        "body",
        "message",
        "internal_note",
        "account_number",
        "email",
        "name",
        "phone",
        "secret",
        "token",
    }
)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_FIELDS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
