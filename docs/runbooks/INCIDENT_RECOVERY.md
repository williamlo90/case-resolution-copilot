# Incident Recovery

Status: Procedure defined; a revision-bound hosted incident exercise has not yet been performed.

Use the release verification and local acceptance matrix to rehearse fail-closed authentication,
honest readiness, model fallback, signed intake rejection, ambiguous action recovery, error
redaction, and production API-document closure. Provider outage, alert delivery, and restore
cutover still require a deployed exercise with separately recorded evidence.

## First Response

1. Assign an incident owner and record start time, affected environment, and correlation IDs.
2. Stop or restrict the smallest affected capability.
3. Preserve logs, audit events, attempts, receipts, configuration versions, and deployment identity.
4. Do not expose secrets or unnecessary customer data in the incident channel.
5. Communicate confirmed facts separately from assumptions.

## Containment By Failure Type

| Failure | Immediate containment |
| --- | --- |
| Database unavailable | Keep readiness unhealthy; stop writes; do not route to an unverified replica |
| Identity unavailable or suspect | Stop authenticated business traffic; never enable deterministic production access |
| Cross-tenant exposure suspected | Disable affected reads/writes, preserve evidence, rotate exposed credentials, begin scoped review |
| Action provider unavailable | Mark connection unavailable and block new execution |
| Action outcome unknown | Block retry and reconcile using recorded external references |
| Model or retrieval failure | Abstain or require human handling; do not fabricate policy support |
| Bad migration or release | Stop rollout and choose reviewed forward fix, application rollback, or verified restore |

## Recovery

- Restore only from a verified artifact or backup.
- Recheck migrations, readiness, tenant isolation, permissions, and redaction before reopening.
- Reconcile every action in running or outcome-unknown state.
- Confirm notification and audit continuity.
- Re-enable providers one at a time.
- Record the exact recovery decision and remaining uncertainty.

## Closure

Close only after customer/business impact, root cause, timeline, affected records, corrective work,
and prevention owner are documented. A service returning `200` is not sufficient closure evidence.
