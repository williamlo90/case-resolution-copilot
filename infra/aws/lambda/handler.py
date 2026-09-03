from __future__ import annotations

import hashlib
import json
import logging
import os
import base64
import re
import uuid
from typing import Any
from urllib.parse import unquote_plus

import boto3

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
AWS_VALIDATION_TASK = "case_resolution.async_jobs.aws_validation"


def handle(event: dict[str, Any], _context: object) -> dict[str, int]:
    s3 = _s3_client()
    sqs = _sqs_client()
    queue_url = os.environ["QUEUE_URL"]
    queue_name = os.environ["QUEUE_NAME"]
    output_prefix = os.environ.get("OUTPUT_PREFIX", "validation-output/")
    max_source_bytes = int(os.environ.get("MAX_SOURCE_BYTES", "1048576"))
    processed = 0

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        size = int(record["s3"]["object"].get("size", 0))
        if size > max_source_bytes:
            raise ValueError(f"Evidence object exceeds {max_source_bytes} bytes")

        response = s3.get_object(Bucket=bucket, Key=key)
        payload = response["Body"].read(max_source_bytes + 1)
        if len(payload) > max_source_bytes:
            raise ValueError(f"Evidence object exceeds {max_source_bytes} bytes")

        digest = hashlib.sha256(payload).hexdigest()
        validation_id = str(json.loads(payload)["validation_id"])
        if re.fullmatch(r"[a-z0-9-]{3,64}", validation_id) is None:
            raise ValueError("validation_id must be a short lowercase identifier")
        manifest = {
            "schema_version": "case-resolution-aws-evidence-v1",
            "source_bucket": bucket,
            "source_key": key,
            "size_bytes": len(payload),
            "sha256": digest,
            "validation_id": validation_id,
        }
        manifest_key = f"{output_prefix}{digest}.json"
        s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=(json.dumps(manifest, sort_keys=True) + "\n").encode(),
            ContentType="application/json",
        )
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=_celery_message(
                task_id=validation_id,
                queue_name=queue_name,
                kwargs={
                    "validation_id": validation_id,
                    "source_bucket": bucket,
                    "source_key": key,
                    "source_sha256": digest,
                },
            ),
        )
        LOGGER.info(
            json.dumps(
                {
                    "event": "evidence_validated",
                    "source_key": key,
                    "manifest_key": manifest_key,
                    "size_bytes": len(payload),
                    "validation_id": validation_id,
                }
            )
        )
        processed += 1

    return {"processed": processed}


def _s3_client() -> Any:
    return boto3.client("s3")


def _sqs_client() -> Any:
    return boto3.client("sqs")


def _celery_message(*, task_id: str, queue_name: str, kwargs: dict[str, str]) -> str:
    encoded_body = base64.b64encode(
        json.dumps(
            [
                [],
                kwargs,
                {"callbacks": None, "errbacks": None, "chain": None, "chord": None},
            ]
        ).encode()
    ).decode()
    message = {
        "body": encoded_body,
        "content-encoding": "utf-8",
        "content-type": "application/json",
        "headers": {
            "lang": "py",
            "task": AWS_VALIDATION_TASK,
            "id": task_id,
            "root_id": task_id,
            "parent_id": None,
            "retries": 0,
            "timelimit": [None, None],
            "argsrepr": "()",
            "kwargsrepr": repr(kwargs),
            "origin": "aws-evidence-validator",
        },
        "properties": {
            "correlation_id": task_id,
            "reply_to": str(uuid.uuid4()),
            "delivery_mode": 2,
            "delivery_info": {"exchange": "", "routing_key": queue_name},
            "priority": 0,
            "body_encoding": "base64",
            "delivery_tag": str(uuid.uuid4()),
        },
    }
    return json.dumps(message, separators=(",", ":"))
