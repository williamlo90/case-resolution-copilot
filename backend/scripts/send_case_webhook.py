import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.integrations.webhook_security import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    sign_webhook,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send one signed case payload to a configured intake endpoint."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--payload", required=True, type=Path)
    arguments = parser.parse_args()

    secret = os.getenv("SUPPORT_COPILOT_CASE_WEBHOOK_SECRET", "").strip()
    if len(secret) < 32:
        raise SystemExit(
            "SUPPORT_COPILOT_CASE_WEBHOOK_SECRET must be set locally with at least 32 characters."
        )
    body = arguments.payload.read_bytes()
    timestamp = int(datetime.now(UTC).timestamp())
    response = httpx.post(
        arguments.url,
        content=body,
        headers={
            "Content-Type": "application/json",
            TIMESTAMP_HEADER: str(timestamp),
            SIGNATURE_HEADER: sign_webhook(
                secret=secret,
                timestamp=timestamp,
                body=body,
            ),
        },
        timeout=10,
    )
    print(f"HTTP {response.status_code}")
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()
