# Case Resolution Copilot

A policy-governed decision workspace for complex support cases.

Case Resolution Copilot helps a support specialist assemble scattered evidence, apply the
correct policy version, prepare a reviewable resolution, obtain human approval, and execute a
controlled action with an auditable recovery path.

> From scattered evidence to an approved, verifiable resolution.

## Product Contract

The [product contract](docs/product/PRODUCT_CONTRACT.md) defines the target users, core workflow,
authority boundaries, MVP, non-goals, domain language, integration boundary, and measurable
acceptance criteria.

The central design rule is simple: AI may organize evidence and draft a recommendation, but
application controls and authorized people decide what may happen.

## Planned Workflow

```text
Case intake -> Evidence review -> Governed policy retrieval -> Decision Brief
            -> Human review -> Controlled action -> Receipt and reconciliation
```

This repository is intentionally product-only at milestone 01. Engineering foundations begin in
the next milestone so technical choices can be evaluated against an explicit contract.
