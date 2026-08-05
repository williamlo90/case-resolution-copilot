# Frontend To Backend Handoff

Status: Superseded Backend Sprint 0 input; generic cutover is complete.
Date: 2026-07-12

## Verdict

Plan A frontend is ready enough to hand off to backend work. Further UI polish is lower leverage than
making the backend return durable support escalation cases that match the current UI contract.

Do not start by renaming tables or routes. Start by preserving the current frontend repository
boundary and returning support-shaped data through compatible endpoints.

## Current frontend contract

The frontend still uses `TaskRepository` and `/tasks` routes as compatibility names. User-facing copy
must read as support escalation cases.

Required list shape:

| Frontend field | Meaning in support product | Backend source |
|---|---|---|
| `id` | Public case ID | Durable opaque case/task public ID |
| `type` | Support case category | Compatibility enum mapped to support labels |
| `summary` | Plain case summary | Case request summary |
| `customer.name` | Customer/account owner name | Customer snapshot |
| `customer.isVip` | VIP support handling flag | Customer snapshot/tier |
| `booking.reference` | Account reference | Account or case account reference |
| `booking.serviceDateLabel` | SLA or due label | SLA deadline display label |
| `status` | Presentation status | Derived from workflow, approval, and information state |
| `dueInMinutes` | SLA urgency | Derived from backend `due_at` |
| `exposure` | Money at risk or proposed impact | Current proposal/risk projection |

Required workspace shape:

| Frontend area | Backend must provide |
|---|---|
| Customer request | Received time, channel, customer message, conversation summary |
| Account context | Immutable account/customer snapshot for the case/run |
| Policy support | Versioned policy title, clause, excerpt, effective date, applicability |
| Safety checks | Business-readable risk label, outcome, and explanation |
| Recommendation | Outcome, amount, confidence, state, decision summary, uncertainty |
| Draft reply | Subject, body, tone, and sendability status |
| Proposed next step | Version, action name, parameters, expected result, approval requirement |
| Activity | Business-readable steps derived from audit/run records |

## Compatibility mapping

Keep these internal enum values temporarily:

| Compatibility enum | User-facing label |
|---|---|
| `refund` | Billing credit |
| `ticket_change` | Account access |
| `booking_issue` | Support exception |
| `needs_approval` | Needs approval |
| `gathering_policy` | Checking policy |
| `needs_information` | Needs customer info |

The frontend must not expose old travel/refund nouns. Historical backend names may remain only in
offline migration storage and mappers, never in the active API.

## API expectations

- Use `/api/cases` and the generic case workspace routes. Legacy task routes are not mounted.
- Return `snake_case` JSON at the API boundary.
- Frontend adapter maps API fields into camelCase domain models.
- Preserve additive compatibility within the generic API contract.
- Do not expose backend workflow enums directly as UI labels.
- Do not expose chain-of-thought, raw provider payloads, secrets, or unnecessary PII.

## Verification policy

Use laptop-safe checks only:

- Backend unit/contract/integration tests for read model and compatibility mapping.
- Frontend adapter/component tests for API responses.
- Optional `/health` or `/ready` smoke only when the backend is already running.

Do not use:

- Playwright.
- Browser automation.
- Automated browser checks against `next dev`.
- Load, stress, concurrency, benchmark loops, watch-mode loops, or worker-heavy verification.

## Backend Sprint 1 ready criteria

Backend Sprint 1 can start when:

- Backend Sprint 0 compatibility strategy is accepted.
- Existing backend state and dirty worktree risks are documented.
- The read model contract above is treated as the source for list/detail support case responses.
- No destructive schema rename is planned.
