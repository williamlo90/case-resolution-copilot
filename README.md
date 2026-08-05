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

## Engineering Baseline

- `frontend/`: Next.js and strict TypeScript.
- `backend/`: FastAPI, Python 3.12, Ruff, Mypy, and Pytest.
- Locked dependency graphs: `pnpm-lock.yaml` and `uv.lock`.
- Resource-safe local commands: serial tests, no watch-mode test runner, and no automatic browser.
- Initial health contract: `GET /api/health/live`.

The architecture begins as a modular monolith. Boundaries may evolve when measured load or team
ownership justifies the cost; speculative services are not part of the baseline.
