# Hosted deterministic acceptance - 2026-08-05

## Verdict

The hosted governed workflow passed its deterministic acceptance scenario:

1. A specialist prepared a source-backed decision brief and submitted it for review.
2. A supervisor reserved and approved the exact proposal version with an attributable reason.
3. The approved action executed once through the deterministic demo adapter.
4. The connected-system receipt and external reference were persisted.
5. A second execution was unavailable and the action reported a duplicate blocker.
6. An auditor could inspect the case, review, approval lineage, attempt, and receipt without receiving mutation controls.

This is evidence for a controlled demo workflow. It is not a claim of validation against a real client, a production action provider, or complete real-business cases.

## Environment

| Component | Acceptance environment |
| --- | --- |
| Frontend | Hosted Next.js deployment on Vercel |
| Backend | Hosted FastAPI deployment on Vercel |
| Database | Neon Postgres development branch |
| Identity | Clerk development instance with live specialist, supervisor, and auditor sessions |
| Decision wording | Deterministic fallback; no OpenAI key was required |
| Action provider | Credential-free deterministic demo adapter |
| Test data | Explicitly labeled synthetic demo case |

## Traceable record chain

| Record | Identifier |
| --- | --- |
| Case | `CS-2050` |
| Resolution proposal | `PRP-E03498558175822A` version 1 |
| Review | `RV-535C4B526D8FE5B3` |
| Proposed action | `PRA-6CAE1C3A76C542FF` |
| Authorized action | `AC-1710C4AB2D34AE32` |
| Execution attempt | `AT-F9FBB4E152E6D8A0` |
| Connected-system receipt | `AR-2074A7F41EC98927` |
| External system reference | `BILLIN-71C11CFFDE6476B4` |

## Acceptance results

| Check | Result | Evidence |
| --- | --- | --- |
| Decision brief contains verified facts and current policy evidence | Pass | Four order facts, two policy items, no blocking information gap |
| Specialist can submit but cannot approve | Pass | Review entered `Ready for review`; specialist review view exposed no decision controls |
| Supervisor reservation and decision are attributable | Pass | Review was reserved and approved with a reason against proposal version 1 |
| Connection freshness is enforced before writes | Pass | A stale health check blocked execution until the administrator service recorded a fresh healthy check |
| Action executes through the approved target once | Pass | One completed attempt and one durable receipt |
| Duplicate execution is prevented | Pass | Execute command disappeared, attempt count remained one, and blocker became `duplicate` |
| Auditor can inspect the immutable lineage | Pass | Auditor could read the review, action attempt, receipt, and system reference |
| Auditor cannot mutate reviews or actions | Pass | No reserve, approve, execute, retry, reconcile, or manual-outcome controls were available |

## Defects found during acceptance

### Blocked connection state was hidden

The first exploratory action used an unconfigured connection. Its detail page rejected the valid
`not_configured` backend value, while the queue silently discarded the backend execution blocker.
The schema contract was corrected to expose `Connection unavailable` in the queue; that correction
is present in the reconstructed source. The original action remained immutable and recorded zero
attempts and no receipt.

### Terminal review was presented as undecided after the case changed

After successful execution updated the case, the approved review page prioritized stale-case messaging over its terminal `approved` status. The UI now presents terminal decisions as complete and separately explains that later source-case changes do not rewrite the recorded review. A regression test covers an approved review with a stale source-case snapshot.

## Screenshots

| State | File |
| --- | --- |
| Specialist decision brief | [01-specialist-decision-brief.png](01-specialist-decision-brief.png) |
| Supervisor review ready | [02-supervisor-review-ready.png](02-supervisor-review-ready.png) |
| Supervisor review approved | [03-supervisor-review-approved.png](03-supervisor-review-approved.png) |
| Action ready to execute | [04-action-ready-to-execute.png](04-action-ready-to-execute.png) |
| Connected-system receipt | [05-action-completed-receipt.png](05-action-completed-receipt.png) |
| Duplicate protection | [06-duplicate-protection.png](06-duplicate-protection.png) |
| Auditor case activity | [07-auditor-case-activity.png](07-auditor-case-activity.png) |
| Auditor read-only action receipt | [08-auditor-read-only-action.png](08-auditor-read-only-action.png) |

Screenshots exclude login forms, passwords, one-time codes, email addresses, and environment secrets.

## Verification performed at capture time

- Focused review-workspace regression tests: 3 passed with one worker.
- Frontend TypeScript check: passed.
- Focused ESLint check: passed.
- Earlier action-contract regression set: 10 passed.
- Earlier full frontend suite after the action-contract fix: 45 files and 135 tests passed with one worker.

## Residual limitation

The case Activity tab currently shows case-subject events only. Review decisions and action attempts remain fully traceable from their dedicated detail pages, but they are not yet aggregated into one case-level timeline. This is a usability improvement, not a blocker for the controlled deterministic workflow proven here.
