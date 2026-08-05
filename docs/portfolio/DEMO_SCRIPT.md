# Case Resolution Copilot - Three-Minute Portfolio Demo

## Preparation

- Use the deployed Administrator account for the broad product tour.
- Keep `CS-2048` and `CS-2047` available as the two case examples.
- Do not execute an external action during a portfolio demonstration.
- If Reviews or Actions are empty, state that the live consequential path is intentionally not
  fabricated and is covered by deterministic authority tests.
- Use the [production walkthrough](../evidence/production-demo/README.md) as a fallback when a live
  session is unavailable. Its screenshots were captured with the read-only Auditor identity.

## 0:00-0:25 - Problem

Say:

> Ordinary support tools help agents reply to tickets. This product focuses on complex cases where
> facts are incomplete, policies matter, financial or customer impact exists, and a supervisor must
> approve the next action.

Show the Cases queue. Point out priority, SLA, risk, owner, and the ability to triage without
opening several systems.

## 0:25-1:20 - Decision Workspace

Open `CS-2048`.

Show:

- Issue summary.
- Verified facts and their sources.
- Information still needed.
- Applicable policy evidence.
- Suggested resolution, uncertainty, impact, and approval requirement.

Say:

> The AI assists with synthesis and wording. Facts, policies, risk checks, and authority remain
> deterministic and auditable.

## 1:20-1:55 - Evidence And Communication

Open the Conversation and Evidence tabs.

Explain that the operator can compare customer communication, business records, and policy
evidence in one workspace. Open Activity and show the audit history.

Say:

> The auditor can inspect and export this record but cannot reply, edit a draft, approve a review,
> or run an action.

## 1:55-2:30 - Governance

Open Policies and show published versions, effective dates, and policy health. Briefly show Team to
explain that Clerk authenticates identity while backend memberships own roles and permissions.

Say:

> Approval is bound to one proposal and evidence version. A later policy change does not rewrite
> the historical decision.

## 2:30-2:50 - Safe Actions

Open Actions.

Explain:

> A timeout is not automatically retried. If the provider may have received the command, the
> system records an unknown outcome and reconciles the receipt before another action is allowed.

Do not claim that a client-owned action provider is active.

## 2:50-3:00 - Evidence And Boundary

Close with:

> The current source passes its serial release gate, while historical hosted evidence records four
> Clerk roles and a bounded workflow. A separate public-data evaluation lane contains 86 records.
> This is a controlled-pilot candidate, not a claim of enterprise-wide production readiness.
