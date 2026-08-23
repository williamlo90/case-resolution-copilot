# Connected Workflow SDLC

Status: Canonical roadmap source  
Adopted: 2026-08-15

This document defines the official Phase 0-8 numbering for the connected inbox and governed RAG
increment. If another planning note assigns a different meaning to a phase number, this document
takes precedence. Implementation status and hosted evidence remain separate because a roadmap is
not proof that a capability has been activated or tested.

The Codex task `019fd73c-8cc0-76b2-a7c9-2a96218f6669` supplied design context. It is not a runtime
service or application dependency.

## Product Direction

The target workflow is:

```text
Email arrives
-> Case is created
-> Evidence is collected
-> Policies are retrieved through RAG
-> AI prepares a Decision Brief
-> A human reviews or approves it
-> The application creates a reply draft
-> The complete process is audited
```

Gmail is the first test-inbox adapter. Provider-neutral boundaries must allow future Zendesk,
Intercom, or Outlook adapters without changing the case domain.

RAG remains in Neon PostgreSQL with pgvector. OpenAI supplies embeddings and bounded narrative
generation; it does not own business data, policy lifecycle, authorization, or deterministic rules.

## Phase 0 - Stabilize The Baseline

- Preserve uncommitted benchmark work.
- Run lightweight unit tests and validators.
- Record the active database, deployment, and configuration state.
- Use a dedicated feature branch when branch isolation is needed.
- Limit the work to five milestone commits so GitHub Actions is not triggered excessively.

Exit gate: the baseline is understood, tests pass, and no secret enters Git.

## Phase 1 - Product And UX Contract

Define the user workflow:

- An agent connects a test inbox.
- A new email becomes a case or is attached to a related case.
- The agent sees facts, evidence, missing information, and applicable policy.
- AI prepares a recommendation, uncertainty, risks, and response draft.
- A reviewer corrects or accepts the recommendation.
- An approver authorizes consequential actions.
- The system creates a Gmail draft and never sends automatically.

First-release non-goals:

- No automatic email sending.
- No automatic refund or financial execution.
- No attempt to replace a helpdesk.
- No production customer data.

Exit gate: workflow, UI language, roles, states, and acceptance criteria are documented.

## Phase 2 - Architecture And Security Design

Define provider-neutral capabilities equivalent to:

```text
InboxConnector
|- connect()
|- sync_threads()
|- fetch_message()
|- create_reply_draft()
`- revoke()
```

Define storage for:

- `inbox_connections`
- `external_threads`
- `external_messages`
- `sync_checkpoints`
- `draft_deliveries`
- `provider_events`

Required controls:

- Tenant isolation.
- OAuth state and CSRF protection.
- Idempotent import and draft creation.
- Incremental sync with bounded retries.
- Provider tokens available only to the backend.
- Auditing for connect, sync, import, review, approval, and draft operations.

Exit gate: ADR, schema, threat model, and rollback design are complete.

## Phase 3 - Gmail Read-Only Integration

- Create and configure the Google Cloud project and Gmail API.
- Configure the OAuth consent screen in testing mode.
- Register the test account.
- Use the minimum read scope for conversation import.
- Import subject, participants, timestamps, body, and attachment metadata.
- Sanitize HTML, signatures, quoted replies, and sensitive data.
- Prevent one external email or thread from creating duplicate cases.
- Expose understandable states: Connected, Syncing, Needs attention, and Disconnected.

Exit gate: one test inbox can create a case idempotently.

Delivery note (2026-08-15): the Phase 3 source implementation and local provider configuration are
complete, but the hosted exit gate is deliberately deferred to Phase 8. The current release policy
allows only one final push after all local phase work is complete, while a real Gmail OAuth callback
requires the new revision to be deployed. This deferral does not count hosted behavior as proven:
Phase 3 remains **implementation complete, hosted acceptance pending** until Phase 8 records the
connect, import, and replay evidence.

## Phase 4 - Governed RAG V2

The RAG corpus contains only official policies and procedures. Emails, invoices, and payment proofs
remain case evidence; they are not policy corpus entries.

Retrieval requirements:

- Versioned policy chunks.
- Metadata for tenant, category, product, region, channel, effective date, and publication status.
- A new 256- or 512-dimensional embedding profile without mutating the legacy index in place.
- Hybrid retrieval using pgvector semantic search and PostgreSQL full-text search.
- Deterministic rank fusion.
- Policy-version and effective-date validation.
- Evidence citations bound to immutable hashes.
- Stale rejection when policy changes during inference.
- Abstention when evidence is insufficient.

OpenAI File Search is not used because policy versioning, tenant isolation, and audit ownership remain
stronger when managed in PostgreSQL.

Exit gate: the frozen retrieval evaluator passes before narrative AI is activated.

Completion note (2026-08-15): Phase 4 passed its frozen evaluator across 15 synthetic cases. V1,
deterministic V2, and OpenAI V2 each recorded `Recall@3 = 1.0`, MRR `1.0`, status accuracy `1.0`,
zero wrong versions, zero unsupported citations, and zero cross-tenant results. The evidence is in
[`backend/evaluations/retrieval_v2`](../../backend/evaluations/retrieval_v2/README.md). This closes
the retrieval implementation and evaluation phase; it does not activate OpenAI V2 in production.

## Phase 5 - Decision And Draft Workflow

- Keep policy applicability, approval, and allowed actions deterministic.
- Use OpenAI only for rationale, uncertainty, summary, and response-draft composition.
- Validate structured output with Pydantic.
- Reject claims that an action happened when it did not.
- Persist policy, evidence, and proposal fingerprints.
- After approval, create a Gmail draft bound to the approved fingerprint.
- Do not expose or invoke a Gmail send operation.

Exit gate: replay creates no duplicate draft and stale approval is rejected.

Completion note (2026-08-18): Phase 5 passed its local gate. The production Decision Brief engine
passed `3/3` synthetic control cases with control preservation `1.000` and no provider calls. The
service-level acceptance lane proves one provider draft on replay, stale approval rejection before
credential or provider access, unknown-outcome reconciliation without write replay, fingerprint
binding, and Auditor denial. The full serial backend gate passed `388` unit/contract tests; Ruff,
strict Mypy across `425` Python files, the repository secret scan, and diff validation also passed.
Evidence and limits are recorded in
[`backend/evaluations/decision_draft`](../../backend/evaluations/decision_draft/README.md). Live
Gmail draft creation remains a single bounded hosted acceptance step in Phase 8; it is not implied
by this synthetic local result.

## Phase 6 - Activate Paid OpenAI Access

Do this only after deterministic implementation and fake-provider tests pass:

1. Create a dedicated OpenAI project.
2. Enable billing with a small pilot budget.
3. Configure usage alerts and limits.
4. Create a project-scoped API key.
5. Store it only in backend environments.

Expected backend settings at the controlled Phase 8 narrative activation gate:

```env
SUPPORT_COPILOT_MODEL_PROVIDER=openai
SUPPORT_COPILOT_EMBEDDING_PROVIDER=deterministic
SUPPORT_COPILOT_OPENAI_API_KEY=replace_locally
SUPPORT_COPILOT_OPENAI_MODEL=gpt-5.6-luna
SUPPORT_COPILOT_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Do not activate OpenAI embeddings implicitly with narrative generation. Governed RAG V2 embedding
and query cutover remains a separate, explicitly measured retrieval decision.

Never use a `NEXT_PUBLIC_*` variable for a secret, commit the key, or send it through chat. Model
availability and pricing are time-sensitive and must be verified against official OpenAI
documentation at activation time. The application enforces per-request input, output, call, and
retry bounds; the user-managed OpenAI project budget controls aggregate spend. Phase 7 records
token usage and cost per case instead of estimating it.

Completion note (2026-08-18): Phase 6 passed its bounded activation canary using synthetic data.
The configured `gpt-5.6-luna` model completed the production evaluator with `3/3` cases passed,
`3/3` safety checks passed, control preservation `1.000`, and exactly `2/2` allowed provider calls.
The missing-policy case skipped the model as designed. A subsequent network-free OpenAI regression
lane passed `46` tests. The narrative gateway now rejects inputs above 24,000 characters before
provider access and caps output at 1,200 tokens. The API key was detected only as a boolean
configuration state and was not printed, copied, or persisted. Sanitized evidence is in
[`backend/evaluations/openai_activation`](../../backend/evaluations/openai_activation/README.md).
The runtime default remains deterministic until Phase 8; token usage and cost-per-case measurement
remain explicit Phase 7 work. Project budget controls are user-managed and were reported configured,
not independently inspected by this repository gate. The final serial backend gate passed `389`
unit/contract tests; Ruff, strict Mypy across `425` Python files, JSON validation, secret scanning,
and diff validation also passed.

## Phase 7 - Verification And Evaluation

Run tests in this order:

- Network-free unit tests.
- Contract tests with fake Gmail and fake OpenAI providers.
- PostgreSQL integration tests against an appropriate non-production Neon target.
- Frozen retrieval benchmark.
- Validate the six available calibration fixtures and preserve answer separation.
- A bounded live OpenAI canary.
- No browser, local server, or parallel worker is required for the local gate.

Initial targets:

- `Recall@3 >= 90%`.
- Wrong policy version: `0`.
- Unsupported citation: `0`.
- Unsafe automatic action: `0`.
- Duplicate case or draft on replay: `0`.
- Approval correctness for critical cases: `100%`.
- Warm authenticated UI LCP: no more than `2.5s`.
- Cost per case is measured rather than guessed.

Completion note (2026-08-19): the local Phase 7 gate passed. Network-free verification passed `331`
unit and `58` contract tests. A guarded migration round-trip and `34` PostgreSQL integration tests
passed on a disposable Neon branch with pgvector active, including the Connected Inbox replay-safe
journey and frozen deterministic RAG V2. The expanded local acceptance matrix passed `64` checks
across `13` areas (`82` selected tests), while the production workflow trace passed `8` scenarios,
`19` proofs, and `21` selected tests. Six matched calibration fixtures passed `9` structural and
answer-separation checks; the timed human comparison was not run and supports no productivity
claim.

The frontend gate passed `160/160` tests plus TypeScript and ESLint without starting Next.js,
Turbopack, Playwright, or a local browser.

The bounded live `gpt-5.6-luna` evaluation passed `3/3` synthetic cases with exactly `2/2` provider
calls and control preservation `1.000`. The provider reported `1,017` input and `278` output tokens;
at the official price checked on 2026-08-18, total cost was `$0.000537`, or `$0.000179` per evaluated
case. Sanitized evidence is in
[`backend/evaluations/phase7_verification`](../../backend/evaluations/phase7_verification/README.md).
Hosted Gmail acceptance, role journeys, warm authenticated UI LCP, and the timed operator benchmark
remain explicit Phase 8 work.

## Phase 8 - Deployment And Operational Readiness

- Apply migrations to the intended Neon environment.
- Deploy with new feature flags disabled.
- Add Vercel environment variables at the final activation gate.
- Activate only one test inbox initially.
- Complete the deferred Phase 3 gate: connect the test inbox, import one allowlisted synthetic
  thread, repeat the import, and prove that only one case, external thread, and message set exist.
- Verify the hosted connection states and audit trail for connect, sync, needs-attention, disconnect,
  and reconnect behavior.
- Test disconnect, token expiry, rate limits, timeouts, and provider outages.
- Prepare kill switches, replay tooling, retention rules, and credential rotation.
- Capture screenshots and benchmark evidence for the portfolio.
- Execute the six-case timed operator benchmark without opening its answer key early.
- Verify warm authenticated UI LCP is no more than `2.5s` with one bounded browser scenario.
- Make claims only from tests that were actually executed.

## Responsibility Split

Codex owns architecture, schema, connectors, RAG V2, UI, automated tests, evaluation harnesses,
migrations, runbooks, deployment configuration, and defect remediation.

The user owns external account authority: creating Google OAuth credentials, enabling OpenAI
billing, creating API keys, entering secrets into Vercel, and completing interactive Gmail sign-in
when requested. Secrets, passwords, and one-time codes must not be sent to Codex chat.

## Commit And Push Policy

The intended milestone groups are:

1. `docs: define connected decision workflow`
2. `feat: add read-only Gmail case ingestion`
3. `feat: add governed hybrid policy retrieval`
4. `feat: add approved Gmail draft delivery`
5. `test: validate connected workflow and operations`

Local edits and verification may accumulate without triggering GitHub Actions. Commit and push only
at the explicitly agreed release point; the current instruction is to wait until all planned local
work is complete before pushing.
