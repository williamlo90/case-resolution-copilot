from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AsyncJobSettings(BaseSettings):
    """Celery transport settings kept separate from application business settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SUPPORT_COPILOT_ASYNC_",
        case_sensitive=False,
        extra="ignore",
    )

    broker_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    result_backend_url: SecretStr | None = None
    sqs_queue_url: SecretStr | None = None
    aws_region: str = Field(default="ap-southeast-1", pattern=r"^[a-z]{2}-[a-z]+-\d$")
    sqs_visibility_timeout_seconds: int = Field(default=180, ge=60, le=43200)
    sqs_polling_interval_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    queue_name: str = Field(
        default="case-resolution-ingestion",
        pattern=r"^[a-zA-Z0-9._-]+$",
        max_length=100,
    )
    delivery_max_retries: int = Field(default=4, ge=0, le=8)
    task_soft_time_limit_seconds: int = Field(default=110, ge=10, le=600)
    task_time_limit_seconds: int = Field(default=120, ge=15, le=660)
    lease_safety_margin_seconds: int = Field(default=30, ge=15, le=300)
    inbox_drain_interval_seconds: int = Field(default=15, ge=5, le=3600)
    policy_index_interval_seconds: int = Field(default=30, ge=5, le=3600)
    result_expires_seconds: int = Field(default=3600, ge=60, le=86400)

    @model_validator(mode="after")
    def validate_transport(self) -> Self:
        broker = self.broker_url.get_secret_value()
        _require_broker_url(broker)
        if self.result_backend_url is not None:
            _require_redis_url(
                self.result_backend_url.get_secret_value(),
                field_name="result backend URL",
            )
        if urlsplit(broker).scheme == "sqs":
            if self.sqs_queue_url is None or not _is_https_url(
                self.sqs_queue_url.get_secret_value()
            ):
                raise ValueError("Celery SQS transport requires an HTTPS queue URL.")
            if self.sqs_visibility_timeout_seconds <= self.lease_duration_seconds():
                raise ValueError("SQS visibility timeout must outlive the durable job lease.")
        if self.task_soft_time_limit_seconds >= self.task_time_limit_seconds:
            raise ValueError("The Celery soft time limit must be lower than the hard limit.")
        return self

    def broker(self) -> str:
        return self.broker_url.get_secret_value()

    def result_backend(self) -> str | None:
        if self.result_backend_url is None:
            if urlsplit(self.broker()).scheme == "sqs":
                return None
            return self.broker()
        return self.result_backend_url.get_secret_value()

    def broker_transport_options(self) -> dict[str, object]:
        if urlsplit(self.broker()).scheme != "sqs":
            return {}
        if self.sqs_queue_url is None:
            raise RuntimeError("Validated SQS settings must include a queue URL.")
        return {
            "region": self.aws_region,
            "visibility_timeout": self.sqs_visibility_timeout_seconds,
            "polling_interval": self.sqs_polling_interval_seconds,
            "predefined_queues": {self.queue_name: {"url": self.sqs_queue_url.get_secret_value()}},
        }

    def lease_duration_seconds(self) -> int:
        """Keep the durable lease alive beyond Celery's forced task termination."""
        return self.task_time_limit_seconds + self.lease_safety_margin_seconds

    def safe_summary(self) -> dict[str, str | int]:
        return {
            "broker_scheme": urlsplit(self.broker()).scheme,
            "queue": self.queue_name,
            "delivery_max_retries": self.delivery_max_retries,
            "task_soft_time_limit_seconds": self.task_soft_time_limit_seconds,
            "task_time_limit_seconds": self.task_time_limit_seconds,
            "lease_duration_seconds": self.lease_duration_seconds(),
            "inbox_drain_interval_seconds": self.inbox_drain_interval_seconds,
            "policy_index_interval_seconds": self.policy_index_interval_seconds,
        }


def _require_redis_url(value: str, *, field_name: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ValueError(f"Celery {field_name} must be a redis:// or rediss:// URL.")


def _require_broker_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme == "sqs" and not parsed.netloc and not parsed.path:
        return
    _require_redis_url(value, field_name="broker URL")


def _is_https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
