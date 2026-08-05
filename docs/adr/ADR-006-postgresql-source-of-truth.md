# ADR-006: PostgreSQL is the durable source of truth

Status: Accepted for Backend Sprint 0

## Decision

Persist business and workflow truth in PostgreSQL. Redis is replaceable queue and coordination
infrastructure; it does not own canonical workflow state, approval authority, execution outcome, or
audit history.

## Rationale

Support action execution must survive API, worker, and queue restarts. Version checks, approval binding,
idempotency, uncertain outcomes, and reconciliation require durable transactional records. A queue
delivery acknowledgment cannot prove the business result.

## Consequences

- Workers load and transition persisted state transactionally.
- Queue messages carry identifiers, not authoritative domain snapshots.
- Duplicate delivery is expected and controlled with database constraints and idempotency keys.
- Redis loss may delay work but cannot erase completed decisions or make uncertain execution appear
  safe.
- LangGraph checkpoints must align with durable domain transitions rather than replace them.

## Alternatives rejected

- **Redis as workflow state:** restart and eviction behavior are incompatible with durable authority.
- **Queue event history as audit log:** delivery events do not capture complete business evidence.
- **Event sourcing:** unnecessary complexity for the current workflow and team size.
