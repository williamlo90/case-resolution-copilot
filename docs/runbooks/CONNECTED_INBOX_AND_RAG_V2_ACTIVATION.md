# Connected Inbox And RAG V2 Activation

Status: local source, migration, deterministic RAG V2, replay-safe inbox workflow, and bounded
OpenAI evaluation gates passed on 19 August 2026. Live Google and hosted-workflow evidence remain
explicit Phase 8 operator gates; all new capabilities stay disabled by default.

## What The Source Provides

- provider-neutral inbox ports plus deterministic and Gmail adapters;
- tenant-scoped OAuth state, encrypted refresh credentials, connection health, and revocation;
- administrator-selected thread import with normalized, deduplicated message evidence;
- bounded incremental sync jobs with leases, finite retries, and recovery states;
- one active sync lease per connection plus transaction-scoped thread serialization;
- mailbox-identity protection that rejects reauthorization with a different provider account;
- review invalidation when imported evidence changes;
- approved Gmail draft creation with idempotency and unknown-outcome reconciliation;
- a Connected Inbox status/read model for the Connections UI;
- a versioned 512-dimensional policy index, lexical GIN index, dense HNSW index, metadata gate,
  reciprocal-rank fusion, diversity limits, and recorded retrieval lineage;
- explicit dense and lexical relevance floors that return no evidence when neither source qualifies;
- a bounded index worker whose provider call runs outside a database transaction.

This does not prove that a live Gmail account, OpenAI account, or hosted database works for the
current revision. Do not present source tests as provider evidence.

## Activation Order

1. Keep every new feature flag `false` and run the credential-free static and unit checks.
2. Apply Alembic revisions `0021` through `0024` to a disposable PostgreSQL database.
3. Verify tenant constraints, migration head, and rollback procedure on that disposable database.
4. Enable deterministic policy indexing and drain a small test corpus.
5. Enable deterministic V2 shadow mode, compare V1/V2 outcomes, then explicitly activate V2.
6. Configure one Google test account and enable read-only inbox connection.
7. Import one allowlisted thread, run one incremental sync, then disconnect and verify history stays
   readable.
8. Enable Gmail draft write-back only after review authorization and reconciliation tests pass.
9. Add OpenAI billing and a project-scoped API key only when the deterministic workflow is stable.
10. Record hosted evidence without secrets, raw customer content, browser traces, or provider tokens.

## Database Gate

Use the guarded disposable-database runner described in
[database migrations](DATABASE_MIGRATIONS.md). Required evidence:

- Alembic reports `20260813_0024` as the single head;
- composite tenant foreign keys and uniqueness constraints reject cross-tenant references;
- the policy profile reaches `ready` only when every current source hash is indexed;
- retrieval readiness is evaluated within the requesting tenant and matching policy scope, so an
  unfinished index in another tenant does not block a complete local scope;
- an expired index or sync lease can be claimed once by a later worker;
- no migration performs a Google or OpenAI network request.

Do not run destructive verification against Neon development or production data.

Observed local gate: Alembic rebuilt a disposable direct Neon branch from base to head, pgvector was
active, and `34/34` PostgreSQL integration tests passed. See
[`backend/evaluations/phase7_verification`](../../backend/evaluations/phase7_verification/README.md).

## Google Test Account Gate

Create a Google Cloud OAuth client for a test project and register the exact frontend callback URL:

```text
https://<host>/connections/inbox/callback
```

Set the Google client ID, client secret, redirect URI, and a generated 32-byte credential-vault key
in the deployment secret manager. Start with:

```text
SUPPORT_COPILOT_INBOX_CONNECTIONS_ENABLED=true
SUPPORT_COPILOT_GMAIL_ADAPTER_ENABLED=true
SUPPORT_COPILOT_INBOX_SCHEDULED_SYNC_ENABLED=false
SUPPORT_COPILOT_GMAIL_PUSH_ENABLED=false
SUPPORT_COPILOT_INBOX_DRAFT_WRITEBACK_ENABLED=false
SUPPORT_COPILOT_INBOX_AI_DATA_TRANSFER_ENABLED=false
```

The read path requests `gmail.readonly`. The draft path additionally requests `gmail.compose`, a
broader restricted scope, so it remains a separate consent and activation step. The application has
no email-send route.

## OpenAI Billing And Key Gate

Use a dedicated OpenAI project, add a payment method, set a low project budget and provider alerts,
then create one project-scoped server key. Store it only as `SUPPORT_COPILOT_OPENAI_API_KEY` in the
local ignored environment file or deployment secret manager.

For a bounded OpenAI index build, keep retrieval on V1 while the worker builds the new profile:

```text
SUPPORT_COPILOT_POLICY_RETRIEVAL_MODE=v1
SUPPORT_COPILOT_POLICY_V2_EMBEDDING_PROVIDER=openai
SUPPORT_COPILOT_POLICY_V2_PROFILE_KEY=openai-text-embedding-3-small-v2-d512
SUPPORT_COPILOT_POLICY_INDEXING_ENABLED=true
```

The OpenAI index worker is bounded and releases its database unit of work before every provider
call. Live OpenAI query retrieval intentionally fails configuration validation in Phase 3: query
activation still requires a two-transaction coordinator so no request holds a database connection
while waiting for OpenAI. Deterministic V2 can be shadowed or activated now; OpenAI V2 query
activation is a later external gate, not an unfinished hidden behavior.

## Acceptance Evidence

Capture one serial hosted journey for each role needed by the workflow. Verify:

- Administrator connects, checks health, selects a thread, pauses, resumes, and disconnects;
- Specialist reads imported evidence but cannot manage connection credentials;
- Supervisor approves the current proposal before one draft is created;
- Auditor can inspect lineage and cannot mutate the connection, review, or draft;
- callback replay, message replay, sync replay, and draft replay do not duplicate state;
- provider timeout and ambiguous draft outcomes fail closed and remain reconcilable;
- account addresses, credential values, raw messages, and API keys are absent from logs and
  screenshots.

Run only static checks and small unit/component tests locally. Hosted browser acceptance remains a
single bounded manual pass under the repository resource-safety policy.

## Rollback

Disable draft write-back first, then scheduled sync, then the Gmail adapter. Pause or disconnect the
connection without deleting imported evidence. For retrieval, switch to `v1`; never delete a V2
profile until all evidence bindings and evaluation records that reference it are retained or
archived according to policy.
