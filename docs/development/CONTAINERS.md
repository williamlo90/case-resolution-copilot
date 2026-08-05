# Development Containers

The optional development stack contains frontend, API, and PostgreSQL/pgvector. It is a local demo
environment, not a production deployment design.

## Resource Gate

Do not build or start this stack on the current laptop without explicit user approval. Compose is
excluded from the default verification path because prior browser/server workflows caused resource
exhaustion.

## Configuration Review

`compose.dev.yaml` uses:

- project name `case-resolution-copilot-dev`;
- `SUPPORT_COPILOT_*` environment variables;
- loopback-only host ports;
- PostgreSQL health before API startup;
- API readiness before frontend startup;
- named volume `case-resolution-copilot-postgres-data`.

The API entrypoint may run migrations, policy ingestion, and demo seeding only when
`SUPPORT_COPILOT_DEV_MIGRATE=true` and `SUPPORT_COPILOT_DEV_SEED=true` are configured.

## Commands

These commands are documentation only until the user approves a container smoke run:

```powershell
docker compose -f compose.dev.yaml up --build
docker compose -f compose.dev.yaml down
```

Deleting the named volume is destructive and must be deliberate:

```powershell
docker compose -f compose.dev.yaml down --volumes
```

## Current Evidence

- Containerfiles and Compose paths are statically reviewed.
- No current support-pivot image build, startup, restart, or persistence smoke has been executed.
- Podman compatibility is unverified.
- Local default credentials are demo values and must never be reused for deployment.
