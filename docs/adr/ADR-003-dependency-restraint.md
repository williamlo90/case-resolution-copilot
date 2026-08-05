# ADR-003: Dependency restraint

Status: Accepted

## Decision

Adopt shadcn/ui selectively. Approve Lucide, TanStack Query/Table, React Hook Form, and Zod when their consuming sprint needs them. Defer Zustand, Framer Motion, Recharts, next-themes, and dark-mode UI.

## Rationale

Dependencies must solve proven product needs. Animation, charts, theme switching, and global state are not Sprint 1 user outcomes.

## Consequences

Semantic tokens must still permit a future dark theme. Deferred dependencies require a later ADR or amendment.

