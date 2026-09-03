from __future__ import annotations

import base64
import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HANDLER_PATH = REPOSITORY_ROOT / "infra" / "aws" / "lambda" / "handler.py"


class _S3:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.writes: list[dict[str, Any]] = []

    def get_object(self, **_kwargs: str) -> dict[str, io.BytesIO]:
        return {"Body": io.BytesIO(self.payload)}

    def put_object(self, **kwargs: Any) -> None:
        self.writes.append(kwargs)


class _Sqs:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, **kwargs: str) -> None:
        self.messages.append(kwargs)


def _handler_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("aws_evidence_handler", HANDLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load AWS evidence handler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lambda_writes_a_content_addressed_evidence_manifest(monkeypatch: Any) -> None:
    module = _handler_module()
    s3 = _S3(b'{"validation_id":"aws-unit"}')
    sqs = _Sqs()
    monkeypatch.setattr(module, "_s3_client", lambda: s3)
    monkeypatch.setattr(module, "_sqs_client", lambda: sqs)
    monkeypatch.setenv("QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setenv("QUEUE_NAME", "validation-queue")

    result = module.handle(
        {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "portfolio-evidence"},
                        "object": {
                            "key": "validation-input%2Fcase.json",
                            "size": len(s3.payload),
                        },
                    }
                }
            ]
        },
        None,
    )

    assert result == {"processed": 1}
    assert len(s3.writes) == 1
    manifest = json.loads(s3.writes[0]["Body"])
    assert manifest["source_key"] == "validation-input/case.json"
    assert manifest["size_bytes"] == len(s3.payload)
    assert len(manifest["sha256"]) == 64
    assert s3.writes[0]["Key"] == f"validation-output/{manifest['sha256']}.json"
    assert manifest["validation_id"] == "aws-unit"
    assert len(sqs.messages) == 1
    envelope = json.loads(sqs.messages[0]["MessageBody"])
    assert envelope["headers"]["task"] == module.AWS_VALIDATION_TASK
    assert envelope["headers"]["id"] == "aws-unit"
    args, kwargs, metadata = json.loads(base64.b64decode(envelope["body"]))
    assert args == []
    assert kwargs["validation_id"] == "aws-unit"
    assert kwargs["source_sha256"] == manifest["sha256"]
    assert metadata["callbacks"] is None


def test_lambda_rejects_an_oversized_evidence_object(monkeypatch: Any) -> None:
    module = _handler_module()
    monkeypatch.setattr(module, "_s3_client", lambda: _S3(b"ignored"))
    monkeypatch.setattr(module, "_sqs_client", lambda: _Sqs())
    monkeypatch.setenv("QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setenv("QUEUE_NAME", "validation-queue")
    monkeypatch.setenv("MAX_SOURCE_BYTES", "4")

    with pytest.raises(ValueError, match="exceeds 4 bytes"):
        module.handle(
            {
                "Records": [
                    {
                        "s3": {
                            "bucket": {"name": "portfolio-evidence"},
                            "object": {"key": "validation-input/large.json", "size": 5},
                        }
                    }
                ]
            },
            None,
        )
