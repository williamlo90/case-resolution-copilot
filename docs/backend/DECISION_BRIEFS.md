# Generic Decision Briefs

Status: Implemented and revalidated in Connected Workflow Phase 5
Date: 18 August 2026

## Purpose

A decision brief turns persisted case context and governed policy evidence into a reviewable,
versioned proposal. It is a decision-support record, not autonomous authority. The backend may
summarize, identify gaps, evaluate deterministic risks, draft a response, and propose actions; it
cannot approve or execute those actions. Approval and Gmail draft creation are separate,
server-enforced workflow stages.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/cases/{case_id}/proposals` | Generate or return the idempotent brief for the current durable input |
| `GET` | `/api/cases/{case_id}/proposals/current` | Read the proposal root's current immutable version |
| `GET` | `/api/cases/{case_id}/proposals/{version}` | Read one immutable historical version |

Generation requires `case:manage` and `policy:read`; reads require `case:read`. Authentication and
authorization run before database access. Cross-tenant reads return `404`.

The generation body contains only:

```json
{
  "expected_case_version": 1
}
```

The server owns organization scope, actor attribution, context and evidence selection, fingerprints,
engine/rule versions, and proposal numbering.

## Decision Record

Each response contains:

- analysis status and exact policy retrieval status;
- source-backed facts and explicit blocking information gaps;
- deterministic risk checks;
- one proposal root and immutable proposal version;
- exact `EVD-*` and `CTX-*` bindings used for that version;
- review-required proposed actions;
- a suggested customer response that cannot overwrite a manually saved draft;
- customer wording tied to the verified evidence and next safe action, without internal control
  labels or premature promises;
- ordered business-safe checkpoints.

`completed` means the deterministic analysis ran with relevant governed policy. It does not mean the
action is approved. `abstained` means usable policy authority was unavailable. A proposal is
`ready_for_review` only when required context is present and current; otherwise it is
`information_needed`.

## Deterministic Safety Rules

- A payment attempt count is not treated as proof of multiple settled charges.
- Refunds require an unused order and confirmation that delivery has not started.
- Account recovery requires recorded identity verification.
- Service correction requires a recorded failed or incomplete outcome.
- Missing, inapplicable, stale, or conflicting policy authority blocks consequential actions.
- Financial impact, high-risk cases, VIP/enterprise customers, and account access trigger human
  review.

The default engine performs no external model call. Model, prompt, graph, and risk-rule version
labels describe deterministic code versions used to reproduce the brief.

## Optional AI Narrative Boundary

OpenAI may rewrite only the rationale, uncertainty, response subject, and response body. The
server-generated facts, policy status, information gaps, risks, outcome, impact, actions, approval
requirements, and proposal state remain deterministic. Provider output is parsed into a strict
Pydantic schema; extra or missing fields fail closed to the built-in deterministic wording.

Every generated narrative field is checked for language that claims a controlled action already
happened. Common active and passive claims such as an issued refund, applied credit, processed
reversal, or sent reply are rejected before persistence. Explicit pending language remains valid.
The rejection creates a safe, auditable checkpoint and does not change the deterministic controls.

## Persistence And Idempotency

The input fingerprint covers case version, request/category, exact business-context fingerprints,
governed evidence fingerprints, and deterministic engine versions. Identical durable input returns
the existing run and proposal version. A changed case version or bound snapshot creates a new
immutable version.

Checkpoints persist only step names, outcomes, safe summaries, and input/output fingerprints. The
schema has no raw prompt, provider payload, reasoning, or chain-of-thought columns.

Review submission persists proposal, context, evidence, risk, and approval-rule fingerprints in one
immutable snapshot. Approved Gmail draft delivery references that review and separately records the
decision, evidence, policy, conversation, and response fingerprints. Its idempotency key binds all
of those authorized inputs, so an identical replay returns the durable delivery instead of invoking
the provider again.

## Migration And Verification

Alembic creates analysis, proposal, context, evidence, risk, and response-draft records directly.
The reconstructed runtime ships no legacy proposal mapper. Deterministic generation, single-flight,
stale-output rejection, transaction-boundary, narrative-boundary, contract, and evaluation tests
run in the serial release gate. PostgreSQL constraints and concurrent lease behavior must still be
rerun through the guarded disposable-database suite for this exact revision.
