# Phase 6 — controlled demo release

Date: October 16, 2026. Status: **engineering packaging gate passed** for the bounded synthetic
demo. The final checkpoint integrates the tested package after Phase 5 benchmark reuse.
This is not a promotion of V2 to the existing hosted application.

## Validation identity

| Evidence | Identity and result |
| --- | --- |
| Isolated container and database run | [38901537078](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38901537078), passed at candidate `5dbbbdb0f5cea7396cbbf40ec20092c97f49b277` |
| Source/dependency quality run | [38899337338](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38899337338), passed before the final container-only fixes |
| Candidate source gate | 12 checks passed: 699 backend tests, 186 frontend tests, Ruff, Mypy over 531 Python files, TypeScript, ESLint, secret scan, migration graph, transport, acceptance and traceability |
| Final checkpoint source gate | 12 checks passed again after the Phase 5 scope revision: 699 backend tests, 186 frontend tests, 525 typed Python files; optional study code is archived locally |
| PostgreSQL integration | 10 passed, zero failures/errors/skips in the isolated candidate run |

The checkpoint's application code, dependency locks, container definitions, Compose configuration,
runtime entrypoint, smoke scripts, and CI definitions match the validated candidate after Git text
normalization. Later differences are documentation and removal of uncommitted optional Phase 5
study preparation. Candidate CI results are attributed to that candidate SHA; they are not a new
run on the final documentation checkpoint. Fresh builds require fresh image identity/scan records.

The final comparison covered 1,123 source/config/lock/workflow files. Local Compose configuration,
PowerShell syntax, documentation links, and staged diff checks passed. Static corpus validation
reported 24 development, three regression, 40 holdout, zero time-study cases, and zero product runs.

## Container and recovery results

- Four Compose services built/started on an isolated Linux/amd64 runner: database,
  migration/seed job, API, and production-built frontend. Three synthetic cases were seeded.
- API/database readiness and the frontend case route passed, including an API restart.
- A logical backup restored into a second disposable database at schema `20261013_0025`.
  Counts matched across twelve core tables, including three cases. The seeded actions, attempts,
  receipts, reviews, and resolution events were empty; this is not a populated action-ledger
  restore or a measured application cutover.
- A deliberately faulted API image exited with code 1. Restoring the exact known-good candidate
  image/config restored readiness with unchanged schema. This proves replacement mechanics,
  not compatibility with a different historical product binary.
- A separate persisted journey recreated the application after an unknown target outcome.
  Unknown state survived, duplicate execution was rejected, retry stayed blocked, and the fresh
  target adapter did not invent a receipt. One attempt and zero receipts remained.
- Disposable containers and volumes were torn down after validation.

| Image | HIGH/CRITICAL findings | Validated image ID |
| --- | ---: | --- |
| API | 0 | `sha256:5a187200ec0869eb0b766608996c8fcf3991140afca9d8b9ee3c8afd09c4bed2` |
| Frontend | 0 | `sha256:aa65935077e1a33e285a720d91dbd762b0e525526d986bf56e59b7120fe2e125` |
| PostgreSQL | 0 | `sha256:a5678051a89a42b055de0ab10622cf287dcb326bceac3820e412189f0b10c421` |

The scan reports also recorded zero secret findings. Raw JSON, JUnit, and smoke output remain in
the linked CI artifacts and ignored local evidence; no runtime credentials are published here.

## Existing hosted route

A bounded unauthenticated HTTP check on October 16 returned:

| Service | Observed result |
| --- | --- |
| Existing Vercel frontend `/cases` | 307 redirect to `/sign-in` |
| Existing Vercel API `/api/health/ready` | 200, `ready`, database `healthy` |
| Both `X-Source-Revision` headers | `dab033c5fb5a69257af76ce41f0553d7fddc665c` |

Repository configuration retains Vercel region `sin1`. The documented hosting remains Vercel
frontend/backend, Neon PostgreSQL, and Clerk identity. This check does not establish a fresh
authenticated Clerk journey, the live database's Alembic revision, or V2 deployment.
No `.vercel/project.json` bindings were found in the checked predecessor checkout and no Vercel
CLI was on PATH. No hosting project, account, or resource was created; no hosted migration,
environment update, or deployment was performed.

## Handoff

Use the [demo release runbook](../../runbooks/PHASE6_DEMO_RELEASE.md) for isolated reproducibility
and the existing-host preview/promotion sequence. The
[readiness tracker](../../production-documentation/PRODUCTION_READINESS_TODO.md) keeps real-provider,
previous-binary compatibility, restore cutover, and cloud reliability activation separate.
The [Phase 5 benchmark](PHASE5_BENCHMARK_REUSE.md) stays complete with its historical scope;
no new operator timing session or new hosting purchase is required by Phase 6.
