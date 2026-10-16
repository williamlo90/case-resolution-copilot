#!/bin/sh
set -eu

if [ -z "${SUPPORT_COPILOT_DATABASE_URL:-}" ] \
  && [ -n "${SUPPORT_COPILOT_DB_HOST:-}" ] \
  && [ -n "${SUPPORT_COPILOT_DB_USERNAME:-}" ] \
  && [ -n "${SUPPORT_COPILOT_DB_PASSWORD:-}" ]; then
  SUPPORT_COPILOT_DATABASE_URL="$(python - <<'PY'
import os
from urllib.parse import quote

username = quote(os.environ["SUPPORT_COPILOT_DB_USERNAME"], safe="")
password = quote(os.environ["SUPPORT_COPILOT_DB_PASSWORD"], safe="")
host = os.environ["SUPPORT_COPILOT_DB_HOST"]
port = os.environ.get("SUPPORT_COPILOT_DB_PORT", "5432")
database = os.environ.get("SUPPORT_COPILOT_DB_NAME", "supportcopilot")
scheme = "postgresql+psycopg"
print(f"{scheme}://{username}:{password}@{host}:{port}/{database}?sslmode=require")
PY
)"
  export SUPPORT_COPILOT_DATABASE_URL
  unset SUPPORT_COPILOT_DB_USERNAME SUPPORT_COPILOT_DB_PASSWORD
fi

if [ -z "${SUPPORT_COPILOT_ASYNC_BROKER_URL:-}" ] \
  && [ -n "${SUPPORT_COPILOT_REDIS_HOST:-}" ] \
  && [ -n "${SUPPORT_COPILOT_REDIS_AUTH_TOKEN:-}" ]; then
  redis_urls="$(python - <<'PY'
import os
from urllib.parse import quote

token = quote(os.environ["SUPPORT_COPILOT_REDIS_AUTH_TOKEN"], safe="")
host = os.environ["SUPPORT_COPILOT_REDIS_HOST"]
port = os.environ.get("SUPPORT_COPILOT_REDIS_PORT", "6379")
scheme = "rediss"
query = "ssl_cert_reqs=required"
print(f"{scheme}://:{token}@{host}:{port}/0?{query}")
print(f"{scheme}://:{token}@{host}:{port}/1?{query}")
PY
)"
  SUPPORT_COPILOT_ASYNC_BROKER_URL="$(printf '%s\n' "$redis_urls" | sed -n '1p')"
  SUPPORT_COPILOT_ASYNC_RESULT_BACKEND_URL="$(printf '%s\n' "$redis_urls" | sed -n '2p')"
  export SUPPORT_COPILOT_ASYNC_BROKER_URL SUPPORT_COPILOT_ASYNC_RESULT_BACKEND_URL
  unset SUPPORT_COPILOT_REDIS_AUTH_TOKEN redis_urls
fi

if [ "${SUPPORT_COPILOT_DEV_MIGRATE:-false}" = "true" ]; then
  .venv/bin/alembic upgrade head
  .venv/bin/python -m scripts.ingest_policies
fi

if [ "${SUPPORT_COPILOT_DEV_SEED:-false}" = "true" ]; then
  .venv/bin/python -m scripts.seed_identity
  .venv/bin/python -m scripts.seed_cases
  .venv/bin/python -m scripts.seed_policies
  .venv/bin/python -m scripts.seed_connections
  .venv/bin/python -m scripts.seed_operational_settings
  .venv/bin/python -m scripts.seed_quality
  .venv/bin/python -m scripts.project_notifications
fi

exec "$@"
