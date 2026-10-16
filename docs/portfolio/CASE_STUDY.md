# Case Resolution Copilot

Case Resolution Copilot helps support operators resolve billing, refund and account-access cases
whose facts are spread across conversations, business records and changing policies. It combines
a review workspace with deterministic authorization and outcome checks.

## Operator workflow

The operator inspects evidence and the applicable SOP, prepares a source-linked Decision Brief,
and obtains human approval for consequential changes. The system executes the approved payload,
reads the target state back, and permits closure only after verification and recorded communication.
Cases requiring specialist handling are routed and acknowledged; reopening preserves the earlier
resolution history. Unknown target outcomes block blind retry.

The Next.js workspace connects to a tenant-scoped FastAPI/PostgreSQL backend. LangGraph coordinates
the decision flow; optional OpenAI wording cannot grant approval or override application controls.
Typed, dated SOP rules govern refund windows, ownership proof and escalation thresholds. Policy,
evidence or payload changes invalidate stale authority.

## Measured results

| Evaluation | Result and scope |
| --- | --- |
| [V2 product holdout](../evidence/case-resolution-v2/RESULTS.md) | 40/40 policy-correct and correct-completion outcomes; 19/19 verified actions and 21/21 acknowledged escalations on synthetic targets |
| [Dated SOP replay](../evidence/case-resolution-v2/results/sop-replay.json) | 18/18 exposed observations across six cases, three rule families and three dated versions per family |
| [Earlier workflow benchmark](../evidence/developer-workflow-benchmark/REPORT.md) | Raw median 95 s Copilot vs 582 s manual, 83.7% lower; one developer and three matched pairs; complete outcomes 3/3 vs 0/3 |
| [Release validation](../evidence/case-resolution-v2/PHASE6_RELEASE.md) | 699 backend and 186 frontend tests; ten PostgreSQL release journeys; startup/restart, seeded restore, image/config recovery, and zero HIGH/CRITICAL findings across three demo images |

The holdout exercised actual PostgreSQL-backed APIs with deterministic decisions and synthetic
action targets. Labels were agent-authored and agent-reviewed. Results describe these scenarios,
not general model accuracy or real-client outcomes. The earlier timing benchmark is separate;
it does not establish speedup between equally successful V2 resolutions.

## Engineering decisions

- **Verify outcomes:** receipts acknowledge requests; target read-back must match the operation,
  destination, parameters, amount and effect count before counting success.
- **Preserve authority:** immutable review snapshots bind approval to policy, evidence and payload.
  Restoring old SOP content creates a new version and does not revive an old approval.
- **Recover without repeating effects:** after application recreation, uncertain action state
  remains uncertain unless independent target evidence establishes the outcome.
- **Improve through replay:** a published refund-window rule initially failed to block an invalid
  proposal. Typed predicates corrected the decision and the case became a regression test.
  See the [failure and fix](../evidence/case-resolution-v2/SOP_REVISIONS.md).

## Delivery and review

The always-on demo uses Vercel, Neon and Clerk. Its hosted screenshots show the earlier deployment;
V2 is packaged and validated in isolated CI, with a [hosted-update handoff](../runbooks/PHASE6_DEMO_RELEASE.md).
A separate [September AWS deployment](../evidence/aws-live-validation/README.md) validated ECS/Fargate,
RDS/pgvector, S3/Lambda/SQS/Celery, worker replacement and teardown. That infrastructure evidence is
retained; no new V2 AWS load or production-availability claim is made.

Start with the [evidence index](../evidence/case-resolution-v2/README.md), use the
[demo runbook](../runbooks/PHASE6_DEMO_RELEASE.md) for reproduction, or review the
[application wording](APPLICATION_PACK.md). Live-provider activation, previous-binary compatibility
and application restore cutover remain separate activation gates.
