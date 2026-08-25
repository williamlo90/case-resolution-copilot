# Hosted Benchmark Preflight - 2026-08-24

This record covers environment preparation only. It is not a timed benchmark result and does not
support a productivity, customer-impact, or model-quality claim.

## Tested Revision

- Git branch: `benchmark-validation`
- Git revision: `5d16c3a`
- Vercel environment: Preview
- Database environment: disposable Neon branch
- Operator role: seeded Specialist membership linked to an existing Clerk development identity

No production database, production deployment, or production identity mapping was changed.

## Preflight Results

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend Preview deployment | Pass | Exact revision reached Vercel `Ready` state |
| Backend Preview deployment | Pass | Exact revision reached Vercel `Ready` state |
| Protected service-to-service access | Pass | Preview-to-Preview trusted-source rule accepted short-lived Vercel OIDC tokens |
| Clerk authentication | Pass | Specialist account completed sign-in on the stable Preview branch domain |
| Workspace membership | Pass | Disposable database linked the Clerk subject to seeded member `USR-0001` |
| Case queue | Pass | Exactly three Product B benchmark cases were visible |
| Billing workspace | Pass | Conversation loaded; `4 of 4` connected records loaded; brief preparation control was available |
| Refund workspace | Pass | Conversation loaded; `4 of 4` connected records loaded; brief preparation control was available |
| Account-recovery workspace | Pass | Conversation loaded; `4 of 4` connected records loaded; stale-source warning and brief preparation control were available |
| Audit activity | Pass | Imported-case activity was visible and attributed to the system |
| Backend runtime | Pass | Current session, queue, and case-detail requests returned `200`; no `5xx` was observed |

Observed backend case-detail durations in the inspected runtime log ranged from approximately
`43 ms` to `198 ms`. These are diagnostic samples, not a latency benchmark.

## Resolved Preflight Findings

1. The first visit used a unique deployment domain while the backend authorized only the stable
   branch domain. Those requests correctly failed authentication. The session was reopened on the
   stable Preview branch domain.
2. The fresh disposable database intentionally had no Clerk subject attached to the seeded
   Specialist. The first authenticated request correctly failed workspace access. The subject was
   linked to `USR-0001` in the disposable branch only.
3. After both corrections, current session and case requests returned `200` and all three prepared
   workspaces loaded without a server error.

## Deliberately Not Executed

- `Prepare brief` was not pressed.
- No case command or workflow mutation was submitted.
- OpenAI was not called and no provider cost was incurred.
- `withheld/answer-key.json` was not opened.
- No stopwatch run or result row was recorded.

The application is warm and ready for the six-case operator protocol. The operator must perform
the timed Manual A and Copilot B runs in the frozen order before the scorer can generate a report.
