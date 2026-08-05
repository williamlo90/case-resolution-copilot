import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.tools.redaction import redact

_STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)
_SAFE_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": (
                message
                if _SAFE_EVENT_NAME.fullmatch(message)
                else "unstructured_log_message_redacted"
            ),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS and key not in {"message", "asctime"}:
                payload[key] = redact({key: value})[key]
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)
