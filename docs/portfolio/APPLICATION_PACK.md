# Case Resolution Copilot application pack

Use these statements for CV, LinkedIn and interview preparation. Select the bullets relevant to
the role; this document does not modify the actual CV. Results and scope are linked in the
[evidence index](../evidence/case-resolution-v2/README.md).

## Positioning

Built a policy-governed AI case-resolution system that turns scattered evidence and dated SOPs
into reviewed actions, verifies target outcomes, and preserves an auditable recovery trail.

Best fit: Applied AI Engineer, AI Engineer, Python Backend Engineer, and AI Automation Engineer.

## Applied AI CV bullets

- Built a governed case-resolution system with FastAPI, PostgreSQL/pgvector and LangGraph,
  combining versioned SOP retrieval, human-approved actions, target read-back, acknowledged
  escalation, and auditable case closure/reopening.
- Achieved policy-correct decisions and correct completion on 40/40 sealed held-out synthetic
  cases using PostgreSQL-backed product APIs and deterministic targets; verified 19/19 required
  actions and 21/21 required escalations.
- Recorded 83.7% lower raw median decision-workflow time (582 s to 95 s) in an earlier
  developer-operated benchmark across three matched synthetic case pairs.
- Validated dated SOP behavior through 18/18 exposed replay observations and packaged a Docker
  demo with ten PostgreSQL release tests, bounded restore/restart checks, and zero HIGH/CRITICAL
  findings across three validated demo images.

For a three-bullet CV, choose product, quality, and either timing or reliability to match the role.
The timing benchmark's complete outcomes were 3/3 Copilot versus 0/3 manual; it is descriptive
elapsed time, not speedup between equally successful resolutions. It is separate from the 40-case
V2 quality cohort. Holdout labels were authored and reviewed by the implementation agent.

## Backend and reliability emphasis

- Implemented tenant-scoped authority, immutable approval snapshots, idempotent action execution,
  explicit target verification, and unknown-outcome reconciliation that blocks blind retries.
- Added dated SOP predicates and stale-approval invalidation, preserving pending-operation
  identity and audit history through policy rollback and case reopening.
- Verified additive migration and durable unknown-outcome handling with disposable PostgreSQL;
  validated seeded logical restore and replacement of a faulted API with its known-good image.

## Cloud emphasis

- Built and live-validated a reproducible AWS deployment architecture with ECS/Fargate,
  RDS PostgreSQL/pgvector, S3, Lambda, SQS, CloudFront, IAM, Secrets Manager and CloudWatch,
  including worker replacement, connected-path replay and verified teardown.

This refers to the September 25 infrastructure validation. The always-on demo uses Vercel/Neon;
V2 has not been newly deployed or load-tested on AWS. Do not describe the demo image scan as an
ECR scan of a current AWS release.

## Interview pitch

Complex support cases require evidence, policy interpretation and authorization. I built a
workspace that turns those inputs into a reviewable Decision Brief, then binds approval to the
exact policy, evidence and action payload. The model can help draft wording, but application
controls own eligibility and execution authority. Actions require target read-back before closure;
uncertain outcomes cannot be retried blindly.

I evaluated the actual product APIs on 40 sealed synthetic cases, with 40/40 policy-correct and
correct-completion outcomes. I also tested dated SOP evolution, persisted recovery and reproducible
container packaging. A separate earlier developer benchmark recorded raw medians of 95 seconds
with Copilot and 582 seconds manually. Cloud architecture was validated in a bounded AWS session;
the hosted demo remains on Vercel and Neon.

## LinkedIn or portfolio description

Case Resolution Copilot is a governed AI workspace for billing, refund and account-access cases.
It combines Next.js, FastAPI, PostgreSQL/pgvector, LangGraph and optional OpenAI wording with
versioned policy retrieval, human approval, controlled actions and verified outcomes. V2 adds
dated SOP rules, acknowledged escalation, auditable closure/reopening, a sealed synthetic product
evaluation, and a reproducible Docker release package. Supporting evidence includes a separate
developer workflow benchmark and a live-validated AWS deployment architecture.

## Evidence and wording boundaries

| Statement | Supporting evidence |
| --- | --- |
| 40/40 synthetic holdout | [V2 results and source identity](../evidence/case-resolution-v2/RESULTS.md) |
| 18/18 dated SOP replay | [Exposed replay aggregate](../evidence/case-resolution-v2/results/sop-replay.json) |
| 83.7% lower raw median time | [Original operator benchmark](../evidence/developer-workflow-benchmark/REPORT.md) |
| Release and image checks | [Phase 6 evidence](../evidence/case-resolution-v2/PHASE6_RELEASE.md) |
| AWS architecture live validation | [September 25 record](../evidence/aws-live-validation/README.md) |

Use synthetic/controlled scope where a metric appears. No claim of real-client adoption,
general model accuracy, hands-free case automation, new V2 operator time savings, AWS sustained
load/availability, or measured production RTO/RPO follows from these results. The
[claim ledger](../evidence/case-resolution-v2/CLAIM_LEDGER.md) maps the supported alternatives.
