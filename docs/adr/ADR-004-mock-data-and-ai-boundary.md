# ADR-004: Mock data and AI boundary

Status: Accepted

## Decision

Mock data flows through typed fixtures, named scenarios, and a repository adapter. The frontend never calls model providers, reasons about policy, stores prompts or secrets, or authorizes consequential actions.

## Rationale

This keeps mock implementation replaceable by a backend and prevents presentation logic from becoming an unsafe decision engine.

## Consequences

All mock records are visibly labelled. Client-side permission checks are never described as security enforcement.
