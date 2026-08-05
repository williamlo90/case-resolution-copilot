# ADR-002: Frontend state ownership

Status: Accepted

## Decision

- URL owns filters, sorting, pagination, and shareable navigation state.
- TanStack Query owns asynchronous repository data.
- React Hook Form owns form interaction state.
- Local React state owns disclosure and ephemeral controls.
- Zustand is deferred until a demonstrated cross-route requirement exists.

## Rationale

State stays close to its source of truth and remains inspectable. A global client store would duplicate URL, server, and form state.

