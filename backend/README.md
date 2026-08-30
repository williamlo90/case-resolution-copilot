# Case Resolution Copilot Backend

FastAPI application for tenant-scoped case investigation, governed policy retrieval, human review,
controlled action execution, and attributable quality evidence.

The backend is a modular monolith. Domain, service, persistence, integration, security, evaluation,
and API modules are explicit boundaries inside one deployable service; the repository does not
claim independent microservices or strict clean architecture.

## Runtime Responsibilities

- Authenticate a Clerk session or a deterministic local actor.
- Resolve organization membership and server-owned permissions.
- Ingest and page cases without exposing another tenant's records.
- Retrieve versioned policy evidence with applicability and freshness checks.
- Generate a structured Decision Brief while the database connection is released.
- Bind review authority to an immutable proposal, evidence, risk, and settings snapshot.
- Execute an approved action once, persist its receipt, and reconcile unknown outcomes.
- Project quality, notification, settings, and audit evidence without storing secrets.

The AI provider drafts bounded narrative fields. It cannot grant a permission, make an approval,
change a policy result, or authorize a side effect.

## Structure

```text
app/
|-- analysis/       deterministic and optional model-assisted decision logic
|-- async_jobs/     Celery delivery over PostgreSQL-owned durable job queues
|-- api/            routes, schemas, presenters, middleware, error envelopes
|-- domain/         typed business records, states, and invariants
|-- evaluation/     decision, workflow, benchmark, and SLO evaluators
|-- integrations/   identity, signed webhooks, provider simulators, action gateways
|-- persistence/    SQLAlchemy repositories and transaction boundaries
|-- orchestrators/  LangGraph runtime, LangChain utilities, optional framework prototypes
|-- retrieval/      policy ingestion, filtering, embeddings, and ranking
|-- security/       authentication, authorization, review authority
`-- services/       application use cases
```

PostgreSQL migrations are under `migrations/`; API conventions and deeper contracts are under
`../docs/backend/` and `../docs/api/`.

## Local Setup

Requirements: Python 3.12 and `uv`.

```powershell
uv sync --frozen --group dev
uv run python -m scripts.run_release_verification --list-checks
```

The default release gate is credential-free and serial. It does not start a server, browser,
container, database, or external model call.

For a manually approved API session:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Do not leave the process running after the bounded task is complete.

## Configuration

Use an ignored `backend/.env` or the deployment secret manager. Start from the repository root
`.env.example`; never commit a populated environment file.

Important groups:

- `SUPPORT_COPILOT_DATABASE_URL`: PostgreSQL connection used by the application.
- `SUPPORT_COPILOT_AUTH_MODE`: `deterministic_development` or `provider`.
- `SUPPORT_COPILOT_CLERK_*`: Clerk server credentials and authorized parties.
- `SUPPORT_COPILOT_MODEL_PROVIDER`: deterministic fallback or optional OpenAI narrative provider.
- `SUPPORT_COPILOT_EMBEDDING_PROVIDER`: deterministic or OpenAI embeddings.
- `SUPPORT_COPILOT_CASE_SOURCE_PROVIDER`: deterministic seed or signed case webhook.
- `SUPPORT_COPILOT_ACTION_TARGET_PROVIDER`: deterministic adapter or signed action webhook.
- `SUPPORT_COPILOT_INBOX_*` and `SUPPORT_COPILOT_GMAIL_*`: bounded connected-inbox import,
  synchronization, and approved Gmail draft creation.
- `SUPPORT_COPILOT_POLICY_*`: versioned 512-dimensional hybrid policy index and V1/V2 rollout
  controls.
- `SUPPORT_COPILOT_ASYNC_*`: Redis broker, queue, bounded delivery retries, and task limits for
  Celery workers.

Production configuration fails closed when provider requirements are incomplete. Sensitive values
are represented as secrets, omitted from safe log context, and covered by the repository scan.
Connected Inbox and Policy RAG V2 are disabled by default; use the
[activation checklist](../docs/runbooks/CONNECTED_INBOX_AND_RAG_V2_ACTIVATION.md) instead of
enabling several flags at once.

## Database Safety

Alembic owns the application schema:

```powershell
uv run alembic current
uv run alembic upgrade head
uv run alembic check
```

Database-backed tests are destructive. Run them only through the guarded script and only against a
direct PostgreSQL endpoint whose environment file explicitly declares it disposable:

```powershell
./scripts/run_integration_tests.ps1 -ConnectionOnly
./scripts/run_integration_tests.ps1 -ConfirmDestructiveDisposableDatabase
```

The runner redacts the URL, checks the endpoint identity and TLS, sets the destructive guard only
for the child process, and refuses non-integration paths. Do not point it at development or
production data.

## Verification

Focused commands:

```powershell
uv run ruff check app tests scripts
uv run mypy app tests scripts
uv run pytest -q tests/unit tests/contract
uv run python -m scripts.check_repository_secrets
uv run python -m scripts.run_local_acceptance --validate-only
uv run python -m scripts.run_workflow_traceability --validate-only
```

The aggregate command is:

```powershell
uv run python -m scripts.run_release_verification
```

It fails fast, redacts common secret forms, and reports counts derived from tool output. Integration
tests that need PostgreSQL remain a separate guarded gate; a skip without `TEST_DATABASE_URL` is not
database evidence.

## Evaluation

The repository separates:

- deterministic Decision Brief fixtures;
- designed workflow golden cases;
- blind public-data adapters and labels;
- persisted quality projections;
- controlled-pilot templates for future client evaluation.

See `../docs/backend/EVALUATION_STRATEGY.md` and `benchmarks/public/README.md`. Public benchmark data
does not justify a claim of validation on complete real business cases.

Run the credential-free governed RAG V2 source and latency gate with:

```powershell
uv run python -m scripts.run_wave1_rag_evaluation --require-gate
```

Inspect the orchestrator roles without credentials or model calls:

```powershell
uv run python -m scripts.inspect_orchestrator_frameworks
```

LangGraph is the default runtime. LangChain Core supports bounded prompt/schema-formatting work.
CrewAI and AutoGen live behind isolated prototype commands and are not application dependencies;
see `../docs/architecture/ORCHESTRATOR_FRAMEWORKS.md`.

Run the single-case live validation explicitly from the isolated prototype environment:

```powershell
uv run --with-requirements examples/orchestrator_prototypes/requirements.txt `
  python -m scripts.run_framework_validation
```

This command makes bounded provider calls and writes sanitized evidence without generated narrative
text or credentials. The recorded result is in `../docs/evidence/framework-validation.md`.

## Async Ingestion

Celery delivers scheduled inbox-sync and policy-index work through Redis. PostgreSQL remains the
source of truth for lifecycle state, attempts, leases, duplicate protection, and reprocessing.

```powershell
celery -A app.async_jobs.celery_worker:app worker --loglevel=INFO --concurrency=2
celery -A app.async_jobs.celery_worker:app beat --loglevel=INFO
celery -A app.async_jobs.celery_worker:app inspect ping
```

Run only one Beat scheduler. The root Compose stack keeps Redis, worker, and scheduler behind the
opt-in `async` profile; container startup remains outside the default local verification gate.

## API Surface

Primary route groups:

```text
/api/health
/api/session
/api/organizations
/api/cases
/api/policies
/api/decision-briefs
/api/reviews
/api/actions
/api/connections
/api/connections/{connection_id}/inbox/status
/api/connections/{connection_id}/inbox/threads
/api/connections/{connection_id}/imports
/api/internal/inbox-sync/drain
/api/internal/policy-index/drain
/api/quality
/api/notifications
/api/settings
/api/intake/cases
```

Production disables interactive API documentation. Errors use a correlated envelope and do not
return internal exception details.

## Deployment

`vercel.json` pins the serverless function region to Singapore. `Containerfile` and the root
`compose.dev.yaml` provide an optional development stack. The separate
[AWS-ready architecture](../docs/architecture/AWS_READY_DEPLOYMENT.md) and deployment templates are
reviewable preparation, not evidence that this application has been deployed to AWS.
Container execution is excluded from the default local gate because it is comparatively expensive.

## Remaining External Gates

- Apply and verify migrations on a disposable database for this exact revision.
- Reconnect and verify Clerk, Neon, and Vercel configuration without exposing secrets.
- Exercise signed case and action adapters against client-owned sandboxes.
- Record provider outage, restore cutover, hosted latency, and alert-delivery evidence.
- Validate complete anonymized client cases before making client-validation claims.
