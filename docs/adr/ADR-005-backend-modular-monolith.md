# ADR-005: Backend modular monolith

Status: Accepted for Backend Sprint 0

## Decision

Build one FastAPI backend as a modular monolith. Domain, API, orchestration, retrieval, tools,
persistence, services, and observability are explicit code boundaries inside one deployable
application.

## Rationale

The flagship proof is one support escalation workflow. Separate services would add deployment,
transaction, contract, and observability complexity before independent scaling or ownership exists.
Code boundaries preserve learning value and allow later extraction without pretending those
operational needs already exist.

## Consequences

- Modules cannot bypass domain services to mutate another module's tables.
- PostgreSQL transactions may protect cross-module invariants.
- The API and background worker may run as separate processes from the same codebase.
- Service extraction requires measured operational or ownership pressure and a new ADR.
- Kubernetes and service-mesh work remain out of scope.

## Alternatives rejected

- **Microservices now:** no evidence of independent scale, ownership, or release requirements.
- **Single unstructured application module:** simpler initially but obscures critical safety
  boundaries.
- **Generic workflow platform:** expands the product beyond the support escalation vertical slice.
