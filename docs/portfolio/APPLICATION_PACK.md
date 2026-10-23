# Case Resolution Copilot - Application Pack

Use this page as the source for CV, LinkedIn, Upwork, GitHub, and interview wording. Keep the
version that fits the role instead of pasting every detail into one application.

## Positioning

**Project category:** Governed AI decision support for operational case resolution.

**Best-fit roles:** AI Engineer, AI Automation Engineer, Python Backend Engineer, Applied AI
Engineer, and AI Platform Engineer.

**One-line description:**

> Built a policy-governed AI case-resolution system that turns fragmented business evidence into
> reviewable decisions, requires human approval for consequential actions, and preserves an
> auditable execution trail.

This is stronger than describing the project as a chatbot or ticket dashboard. The core
engineering problem is controlling how AI participates in decisions that may affect customer
accounts or company funds.

## Thirty-Second Pitch

> Case Resolution Copilot helps an operations team handle cases where the answer depends on
> scattered records, policy versions, missing evidence, and approval limits. I built the product
> with Next.js, FastAPI, PostgreSQL, LangGraph, Celery, and an optional OpenAI narrative layer. The
> application owns the facts, risk checks, permissions, approval state, and action execution, so
> the model cannot approve its own recommendation. I validated it with a 20-execution regression
> suite, a bounded OpenAI canary, guarded PostgreSQL workflow tests, and a short-lived AWS
> deployment architecture.

## Two-Minute Interview Version

> I built Case Resolution Copilot because difficult customer cases are usually decision problems,
> not reply-writing problems. Evidence may be split across conversations, payments, orders, and
> policy documents. A model can write a convincing answer while using stale rules or missing an
> approval boundary.
>
> The system creates a Decision Brief containing verified facts, missing information, applicable
> policy, risk checks, uncertainty, a proposed action, and a response draft. LangGraph coordinates
> the decision flow, but deterministic application code owns policy status, evidence binding,
> permissions, and approval rules. Consequential actions are snapshot-bound, idempotent, and
> produce durable receipts. If an external action times out with an unknown outcome, the system
> blocks blind retry and requires reconciliation.
>
> The backend is a FastAPI modular monolith backed by PostgreSQL and pgvector. Celery handles
> asynchronous ingestion using Redis locally and SQS in the AWS profile. I also built a bounded
> evaluation system. The final development-set regression passed 20 of 20 observations, a
> two-call OpenAI canary preserved deterministic controls in all three test cases, and four
> targeted PostgreSQL scenarios validated conflict blocking, immutable approvals, exactly-once
> execution, and unknown-outcome recovery. The always-on demo uses Vercel and Neon; AWS was a
> live-validated, teardown-safe deployment architecture rather than permanent production hosting.

## CV Bullets

### AI Engineer

- Built a policy-governed AI decision system with LangGraph and an optional OpenAI narrative
  layer, keeping facts, policy applicability, risk, approval, and execution authority in
  deterministic application controls.
- Designed an auditable evaluation pipeline with frozen inputs and labels, SHA-256 integrity
  checks, 20 repeated regression observations, a two-call provider canary, measured token cost,
  and explicit claim boundaries.
- Implemented governed retrieval over PostgreSQL/pgvector with versioned policy evidence,
  expected-source checks, abstention behavior, and traceable source bindings.

### Python Backend Engineer

- Developed a tenant-scoped FastAPI and PostgreSQL backend with Clerk authentication, RBAC,
  immutable review snapshots, optimistic concurrency, idempotency, durable action receipts, and
  unknown-outcome reconciliation.
- Implemented asynchronous ingestion with Celery, Redis/SQS delivery profiles, finite retries,
  duplicate protection, job status, dead-letter handling, and controlled reprocessing.
- Validated critical stateful paths against migrated PostgreSQL: conflicting evidence fails
  closed, approval remains bound to an immutable proposal, execution is exactly once, and unknown
  outcomes cannot be retried blindly.

### AI Automation And Cloud

- Built and live-validated a reproducible AWS deployment architecture using ECS/Fargate, RDS
  PostgreSQL with pgvector, S3, Lambda, SQS, CloudFront, IAM, Secrets Manager, and CloudWatch, with
  infrastructure designed for safe teardown and redeployment.
- Separated the always-on Vercel/Neon demo from a short-lived AWS validation environment, allowing
  cloud evidence without carrying unnecessary portfolio infrastructure cost.
- Added structured health checks, correlated logs, queue failure visibility, migration tasks,
  least-privilege boundaries, and automated teardown controls.

## LinkedIn Project Description

> Case Resolution Copilot is a production-oriented AI decision-support portfolio project for
> complex operational cases. It combines a Next.js workspace with a FastAPI/PostgreSQL backend,
> governed policy retrieval, LangGraph orchestration, optional OpenAI-assisted wording, human
> approval, and controlled action execution. The project includes Celery-based asynchronous
> ingestion, idempotency and reconciliation controls, four-role RBAC, auditable evaluation, and a
> live-validated AWS deployment architecture. Evaluation evidence includes a 20-execution
> synthetic regression suite, a bounded provider canary, targeted PostgreSQL workflow validation,
> and a developer-operated matched workflow benchmark.

## Upwork Portfolio Description

### Title

AI Case Resolution System with FastAPI, RAG, Human Approval, and AWS Architecture

### Overview

> I designed and built an AI-assisted operations system for cases that require evidence review,
> policy interpretation, risk checks, and management approval. Instead of allowing an LLM to make
> uncontrolled decisions, the system uses AI only for bounded assistance while the backend
> enforces source traceability, authorization, approval state, idempotency, and auditability.
>
> The solution includes a Next.js application, FastAPI APIs, PostgreSQL/pgvector retrieval,
> LangGraph orchestration, OpenAI integration, Clerk authentication, Celery background jobs,
> controlled external actions, and AWS-ready infrastructure. It is relevant to customer
> operations, refund and billing review, account recovery, compliance workflows, internal service
> requests, and other approval-heavy business processes.

### Client-Relevant Capabilities

- Convert conversations and business records into a structured decision brief.
- Retrieve and cite the policy version applicable to a case.
- Detect missing or conflicting evidence and abstain safely.
- Route consequential decisions through role-based human approval.
- Execute approved actions with idempotency, receipts, and recovery controls.
- Process ingestion and indexing work asynchronously with observable job status.
- Evaluate AI behavior with repeatable fixtures, safety checks, latency, and cost evidence.

## GitHub Metadata

**Repository description:**

> Governed AI case-resolution workspace with FastAPI, Next.js, LangGraph, PostgreSQL/pgvector,
> human approval, controlled actions, auditable evaluation, and AWS deployment architecture.

**Suggested topics:**

`ai-engineering`, `fastapi`, `nextjs`, `langgraph`, `rag`, `postgresql`, `pgvector`, `celery`,
`human-in-the-loop`, `ai-agents`, `aws`, `evaluation`

## Evidence Cheat Sheet

| Claim | Evidence | Meaning |
| --- | --- | --- |
| `20/20` regression observations passed | [Evaluation V1](../evidence/case-resolution-evaluation-v1/README.md) | Implemented control-state, source-coverage, risk, escalation-disposition, action-type/safety, schema, and consistency checks passed on the final development-set regression |
| `3/3` OpenAI canary cases passed | [Provider canary](../evidence/case-resolution-evaluation-v1/provider-canary-results.json) | Two bounded provider calls preserved server-owned controls; one policy-missing case correctly skipped the provider |
| `4/4` targeted database scenarios passed | [Persisted workflow evidence](../evidence/case-resolution-evaluation-v1/persisted-workflow-results.json) | Critical review and controlled-action paths behaved correctly against migrated PostgreSQL |
| `83.7%` lower raw median elapsed time | [Workflow benchmark](../evidence/developer-workflow-benchmark/REPORT.md) | One developer completed three matched synthetic cases per condition; this is descriptive, not a population estimate |
| AWS architecture live-validated | [AWS evidence](../evidence/aws-live-validation/README.md) | A bounded short-lived environment passed connected checks and verified teardown; the product is not permanently hosted on AWS |

## Interview Proof Map

When asked about architecture, start with the authority boundary: AI drafts, application controls
decide what is eligible, and a human authorizes consequential actions.

When asked about reliability, explain idempotency, immutable review snapshots, single-flight
generation, finite retries, durable receipts, and unknown-outcome reconciliation.

When asked about RAG, explain policy filtering by tenant and applicability before similarity,
versioned source bindings, source freshness, abstention, and expected-source evaluation.

When asked about agents, explain why LangGraph is the production orchestration boundary while
CrewAI and AutoGen remain isolated comparison prototypes. Framework count is not the achievement;
controlled state transitions are.

When asked about AWS, distinguish a live-validated deployment architecture from an always-on
production claim. Explain ECS/Fargate for API and workers, RDS/pgvector for durable state and
retrieval, SQS for Celery delivery, S3/Lambda for evidence workflows, Secrets Manager for runtime
credentials, and CloudWatch for operations.

When asked about evaluation, separate the four forms of evidence: deterministic development-set
regression, provider safety canary, persisted workflow tests, and human workflow timing.

## Claims To Avoid

Do not say the project is generally production-ready, validated on real client cases, permanently
hosted on AWS, or proven to improve customer productivity at population scale.

Do not describe `20/20` as general model accuracy. It is a post-fix synthetic regression result on
implemented deterministic checks.

Do not describe the `83.7%` timing result as a guaranteed productivity improvement. It is a
developer-operated matched benchmark with three synthetic cases per condition.

## Recommended Application Strategy

1. Lead with the one-line description and one role-specific group of CV bullets.
2. Link the hosted application and engineering case study.
3. Use one evidence number in the application, not all of them.
4. For AI roles, emphasize governed model behavior and evaluation.
5. For backend roles, emphasize state, concurrency, idempotency, and recovery.
6. For automation or cloud roles, emphasize async jobs and the live-validated AWS architecture.
7. Keep the deeper methodology links available for technical interviews.
