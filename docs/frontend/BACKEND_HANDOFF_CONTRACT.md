# Frontend To Backend Handoff Contract

Date: 23 July 2026
Frontend contract status: generic API cutover complete, automated lightweight checks passed, manual
user acceptance and external activation pending.

## 1. Source Of Truth

Backend responses must map to the frontend domain schemas before reaching feature components:

- Cases: `frontend/src/domain/cases/case.ts`
- Reviews: `frontend/src/domain/reviews/review.ts`
- Actions: `frontend/src/domain/actions/action.ts`
- Policies: `frontend/src/domain/policies/policy.ts`
- Quality: `frontend/src/domain/quality/quality.ts`
- Administration: `frontend/src/domain/administration/administration.ts`

Mock repositories are explicit opt-in boundaries, not backend specifications. Primary operational
routes do not import fixtures or legacy task repositories. Legacy task and travel fields remain
restricted to redirects, diagnostics, migration adapters, and historical tests.

## 2. Required Read Contracts

| Product route | Required backend query |
| --- | --- |
| `/cases` | List generic case summaries with explicit owner, update time, SLA, risk, and source freshness. |
| `/cases/:caseId` | Return the full case workspace, including facts, missing information, evidence, risks, proposal, draft, activity, and allowed commands. |
| `/reviews` | List submitted immutable proposal snapshots by impact, reason, policy state, uncertainty, age, freshness, status, and reservation. |
| `/reviews/:reviewId` | Return the exact case, context, policy, risk-rule, proposal, and action versions being authorized. |
| `/actions` | List approved actions with target, impact, status, attempt count, owner, and recovery requirement. |
| `/actions/:actionId` | Return authority, typed parameters, target health, idempotency key, attempts, receipt, and expected/observed outcomes. |
| `/policies` | List lifecycle, ownership, applicability, source, health, effective window, and usage count. |
| `/policies/:policyId` | Return immutable versions, clauses, source text, effective windows, and version-bound case references. |
| `/quality` | Return business quality metrics and attributable evaluated-case evidence. |
| `/connections` | Return capabilities, environment, health, and credential status; never return secret values. |
| `/team` | Return membership, role, status, and explicit authority. |
| `/settings/:section` | Return versioned organization governance settings. |

## 3. Required Command Contracts

| Command | Required backend behavior |
| --- | --- |
| Assign case | Authorize, update owner atomically, and return the authoritative case version. |
| Save response draft | Preserve user input and return draft version and update time. |
| Submit for review | Freeze proposal, context, policy, and risk-rule versions; return the new review identity. |
| Reserve review | Enforce one active reservation with expiry and return reservation identity. |
| Decide review | Require actor, authority, exact snapshot fingerprint, decision, and reason; return an immutable decision receipt. |
| Execute action | Require an approved unexpired proposal, permission, healthy target, and idempotency key; return attempt identity immediately. |
| Reconcile outcome | Check the target using recorded references without issuing another write. |
| Retry safe failure | Permit only when evidence proves no target change occurred and the connection is eligible. |
| Create policy draft | Copy from the selected version while leaving published and historical versions immutable. |
| Publish/schedule/retire policy | Return a lifecycle receipt and preserve prior effective versions. |
| Test connection | Return a health-check receipt; never echo credentials. |
| Change member role/settings | Enforce administrator authority and optimistic concurrency. |

## 4. State And Failure Semantics

- `409 Conflict`: return current entity version and a reason; the UI must review current data rather
  than silently overwrite it.
- `403 Forbidden`: reveal no restricted entity content or unavailable command parameters.
- `422 Unprocessable Entity`: return field-level or command-level business validation in plain language.
- `424 Failed Dependency` or equivalent domain response: preserve input and identify the unavailable
  connection or service.
- Consequential success returns a durable receipt or authoritative state. A message alone is not proof.
- Safe failure and outcome unknown are different states. Unknown outcome must not expose blind retry.
- Stale review snapshots, expired approvals, changed proposals, duplicate actions, and missing authority
  are hard execution stops.
- Timestamps are ISO 8601 UTC. Money uses numeric amount plus ISO 4217 currency. No synthetic owner,
  timestamp, freshness, receipt, or external reference is allowed in API mode.

## 5. Compatibility And Migration

- `/tasks` redirects to `/cases`.
- Legacy `TaskSummary` and `TaskWorkspace` are no longer inputs to the active case repository.
- Legacy RF/TC/BI identifiers remain internal `sourceId`; public case identity is `CS-*`.
- Legacy task approval routes redirect to `/reviews/:reviewId` after case-to-review lookup.
- Technical run details remain a restricted diagnostic view and are not the primary product model.

## 6. Credential Activation Order

1. Complete backend services and migrations with deterministic fixtures and simulated providers.
2. Run unit, contract, migration, authorization, idempotency, and failure-state tests without real secrets.
3. Add `.env` values only after service boundaries and redaction rules are verified.
4. Validate PostgreSQL, identity, model, support, billing, and other providers one at a time.
5. Run post-credential integration, security, redaction, audit, and manual end-to-end acceptance.

The frontend remains usable without external credentials through deterministic backend data or
explicit `SUPPORT_COPILOT_DATA_MODE=mock`.

## 7. Frontend Freeze Evidence

- TypeScript: passed.
- ESLint: passed.
- Vitest: B8 final count is recorded in `docs/evidence/backend-b8/SPRINT_B8_REVIEW.md`.
- Repository cutover contract: active routes contain no fixture or legacy task repository imports.
- Resource blacklist: respected; no Playwright, browser automation, build, Docker, load, stress,
  concurrency, benchmark, or additional watch process was used.
- Manual role-based acceptance remains required after environment activation.
