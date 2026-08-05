# Case Resolution Copilot

A policy-governed decision workspace for complex customer cases.

Case Resolution Copilot helps a support team assemble scattered evidence, retrieve the applicable
policy version, prepare a reviewable resolution, obtain human approval, and execute a controlled
action with an auditable recovery path. The AI provider may draft bounded narrative from a
server-generated control record;
application controls and authorized people decide what may happen.

> From scattered evidence to an approved, verifiable resolution.

[![Decision Brief workspace](docs/evidence/production-demo/02-decision-brief.png)](docs/evidence/production-demo/README.md)

[Hosted application](https://ai-support-escalation-copilot.vercel.app) | [Engineering case study](docs/portfolio/CASE_STUDY.md) | [Three-minute demo](docs/portfolio/DEMO_SCRIPT.md)

The hosted application is invite-only. The public walkthrough contains labelled demo data only.

## Why It Exists

Complex cases rarely live in one message. Facts can be split across conversations, payments,
orders, account records, policies, and internal notes. A fast AI answer can sound certain while
using stale policy, overlooking missing evidence, or proposing an action nobody authorized.

This product is organized around a more useful set of questions:

> What is known, what is missing, which policy applies, what could go wrong, and who must approve
> the next step?

## Product Workflow

```text
Case intake -> Triage -> Evidence and policy review -> Decision Brief
            -> Human review -> Controlled action -> Receipt and reconciliation
```

- **Cases** prioritizes work by risk, SLA, status, ownership, and source freshness.
- **Decision Brief** separates verified facts, missing information, uncertainty, and recommendation.
- **Conversation and Evidence** keep business records and policy citations inspectable.
- **Reviews** bind human authority to one immutable proposal and evidence snapshot.
- **Actions** use idempotency, durable receipts, unknown-outcome handling, and reconciliation.
- **Policies and Quality** govern what the system may rely on and how behavior is evaluated.

## Product Tour

<table>
  <tr>
    <td width="50%">
      <a href="docs/evidence/production-demo/01-cases-queue.png"><img src="docs/evidence/production-demo/01-cases-queue.png" alt="Cases queue"></a><br>
      <strong>Operational queue</strong><br>
      Triage by risk, SLA, ownership, status, and source freshness.
    </td>
    <td width="50%">
      <a href="docs/evidence/production-demo/02-decision-brief.png"><img src="docs/evidence/production-demo/02-decision-brief.png" alt="Decision Brief"></a><br>
      <strong>Decision Brief</strong><br>
      Verified facts, missing evidence, uncertainty, and the review boundary.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <a href="docs/evidence/production-demo/04-evidence.png"><img src="docs/evidence/production-demo/04-evidence.png" alt="Policy and business evidence"></a><br>
      <strong>Traceable evidence</strong><br>
      Policy clauses and business records remain connected to sources.
    </td>
    <td width="50%">
      <a href="docs/evidence/hosted-e2e-acceptance/2026-08-05/05-action-completed-receipt.png"><img src="docs/evidence/hosted-e2e-acceptance/2026-08-05/05-action-completed-receipt.png" alt="Completed controlled action"></a><br>
      <strong>Controlled execution</strong><br>
      Approved actions preserve attempts, receipts, and external references.
    </td>
  </tr>
</table>

The [product walkthrough](docs/evidence/production-demo/README.md) and
[hosted deterministic acceptance](docs/evidence/hosted-e2e-acceptance/2026-08-05/README.md) were
captured from the predecessor hosted deployment of the same product. They prove those observed
states, not the correctness of the current source revision; current source verification is reported
separately below.

## Authority Model

| Layer | Responsibility |
| --- | --- |
| AI provider | Draft structured narrative from bounded case and policy context. |
| Application controls | Enforce tenant scope, policy freshness, evidence binding, permissions, approval state, and action safety. |
| Human reviewer | Accept responsibility for the exact proposal version before a consequential action. |
| External system | Return a receipt or an explicitly unknown outcome that must be reconciled. |

AI confidence cannot grant approval, bypass missing evidence, or authorize a side effect.

## Architecture

```mermaid
flowchart LR
    SOURCE["Support channels and business systems"] --> INTAKE["Signed case intake"]
    INTAKE --> CASES["Tenant-scoped case workspace"]
    CASES --> EVIDENCE["Business evidence"]
    POLICY["Versioned policy corpus"] --> RETRIEVAL["Filtered retrieval"]
    EVIDENCE --> BRIEF["Decision Brief engine"]
    RETRIEVAL --> BRIEF
    BRIEF --> REVIEW["Human approval"]
    REVIEW --> ACTION["Controlled action adapter"]
    ACTION --> RECEIPT["Receipt and reconciliation"]
    CASES --> AUDIT["Audit and quality evidence"]
    REVIEW --> AUDIT
    RECEIPT --> AUDIT
    CLERK["Clerk identity"] --> CASES
    DB["PostgreSQL"] --> CASES
    DB --> POLICY
```

The stack is Next.js, TypeScript, FastAPI, PostgreSQL/pgvector, Clerk, and an optional OpenAI
narrative provider. It is a modular monolith, not a microservice system. Deterministic providers
keep repository verification independent of paid credentials.

## Current Verification

Verification is recorded in two layers so a focused hardening rerun is not presented as a second
full release run:

| Evidence layer | Result |
| --- | ---: |
| Reconstruction baseline | 12 / 12 serial release checks passed before the final audit corrections |
| Release-hardening static checks | Ruff, Mypy over 195 application files, TypeScript, and ESLint passed |
| Release-hardening regressions | 73 focused backend tests and 4 focused frontend tests passed |
| Baseline acceptance matrix | 54 controls / 71 variants passed |
| Baseline workflow traceability | 8 scenarios / 19 proofs / 21 variants passed |

The PostgreSQL integration suite is present behind a destructive disposable-database guard, but it
has not been rerun for this reconstructed revision. Historical database and hosted results are not
counted as current source evidence. The full release verifier should be rerun before promotion; the
focused hardening gate is not a substitute for that release decision.

The [GitHub quality gate](https://github.com/williamlo90/case-resolution-copilot/actions/workflows/quality-gate.yml)
runs on pull requests or manual dispatch, never on every push. It adds dependency audits and a
production Next.js build. This policy avoids accidental GitHub Actions usage while preserving a
review gate.

## Run Without Paid Credentials

Requirements: Python 3.12, `uv`, Node.js, and `pnpm`.

```powershell
git clone https://github.com/williamlo90/case-resolution-copilot.git
cd case-resolution-copilot

cd backend
uv sync --frozen --group dev
uv run python -m scripts.run_release_verification
```

The verifier runs serially and starts no browser, application server, container, database, or
external model call. See the [backend guide](backend/README.md), [frontend guide](frontend/README.md),
and [resource policy](RESOURCE_SAFETY_POLICY.md).

## Claim Boundaries

- This is a production-oriented portfolio project and controlled-pilot candidate, not a claim of
  general production readiness.
- The hosted identity setup uses an invite-only Clerk development instance.
- No client-owned case source or controlled-action sandbox is connected.
- Public benchmark records and synthetic controls test the evaluation system; they are not complete
  client cases and do not prove customer impact.
- Current external gates include disposable-database verification, provider failure drills, restore
  cutover, production telemetry, accessibility research, penetration testing, bounded load testing,
  and complete anonymized client-case validation.

## Documentation

- [Documentation index](docs/README.md)
- [Product contract](docs/product/PRODUCT_CONTRACT.md)
- [UX architecture](docs/product/UX_ARCHITECTURE.md)
- [Engineering case study](docs/portfolio/CASE_STUDY.md)
- [API conventions](docs/api/CONVENTIONS.md)
- [Evaluation strategy](docs/backend/EVALUATION_STRATEGY.md)
- [Controlled pilot runbook](docs/pilot/PILOT_RUNBOOK.md)
- [Security hardening](docs/runbooks/SECURITY_HARDENING.md)
- [Post-environment verification](docs/runbooks/POST_ENV_VERIFICATION.md)
