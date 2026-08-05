#!/bin/sh
set -eu

if [ "${SUPPORT_COPILOT_DEV_MIGRATE:-false}" = "true" ]; then
  uv run alembic upgrade head
  uv run python scripts/ingest_policies.py
fi

if [ "${SUPPORT_COPILOT_DEV_SEED:-false}" = "true" ]; then
  uv run python scripts/seed_identity.py
  uv run python scripts/seed_cases.py
  uv run python scripts/seed_policies.py
  uv run python scripts/seed_connections.py
  uv run python scripts/seed_operational_settings.py
  uv run python scripts/seed_quality.py
  uv run python scripts/project_notifications.py
fi

exec "$@"
