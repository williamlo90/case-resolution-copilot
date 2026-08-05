# ADR-001: Frontend location and framework

Status: Accepted for Sprint 1

## Decision

Create the frontend in `frontend/` using pnpm, Node.js 22, Next.js 16 App Router, strict TypeScript, and Tailwind CSS.

## Rationale

The separate folder preserves a clean future boundary with the planned Python backend. App Router supports route layouts, server/client boundaries, and loading/error states without inventing a custom application framework.

## Consequences

Frontend and backend contracts must remain explicit. Next.js routing concerns cannot enter domain contracts.

