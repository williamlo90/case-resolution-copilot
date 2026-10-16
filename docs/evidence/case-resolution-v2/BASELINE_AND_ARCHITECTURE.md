# Phase 0 baseline and architecture delta

Inspected 2026-10-13. Evidence below is read from source/artifacts; historical tests were not
rerun as part of the audit. Resource policy permits small serial unit/static checks only here.

## Git and preserved work

The requested active checkout `case-resolution-copilot-rebuild` is on local main `2a8175b`.
GitHub main was `dab033c5fb5a69257af76ce41f0553d7fddc665c`. Local main has prior merge/harness
commits not in GitHub main and lacks later upstream changes; no reset/merge/stash was performed.
In particular `1a88dbb` remains an ancestor of that main checkout even after the separate
production-validation worktree was archived. Archiving that worktree did not remove this ancestor.

For this checkpoint, `case-resolution-v2` starts from GitHub main `dab033c` in the sibling
`case-resolution-copilot-v2` worktree. This avoids publishing the old harness as ancestry of
the new checkpoint. Both worktrees belong to the same Git repository. The original spec and
baseline hashes/status remain ignored in the main checkout under `local/implementation-specs/`.
This is the execution-location mapping for the spec; the original main checkout remains intact.

Existing local work belongs to the prior AWS validation effort; authorship was not inferred
from Git metadata. It was inspected for scope and left untouched:

- `backend/app/config.py`, `production_validation/hooks.py`, and the fault unit test reject
  injected fault commands without an active validation run.
- k6 Docker/entrypoint/main changes upgrade image packages, require a summary, record percentiles,
  count failed reads accurately, and classify expected concurrency conflicts.
- AWS runtime/load-image/lane/DLQ scripts change session fields, image scan parsing, bounded
  deadlines/stop handling, and isolated transport-level DLQ probes.
- `infra/aws/test/load-runner.test.ts` is untracked and tests those measurement behaviors.
- Backup runbook and frontend package/workspace files appear modified in status but have no
  substantive patch in the inspected diff (line-ending/index representation); preserve bytes.

The ignored production-readiness TODO records image blockers (2 critical, 7 high at its earlier
scan), pending fault lifetime/restore/alerts/identity work, and teardown verified on October 2.
These are historical records, not a fresh scan or cloud inspection. No load run is recorded.
Phase 7 must re-inspect and integrate this work intentionally; it is outside Phase 0.

## Existing evidence

| Evidence | Status and interpretation |
| --- | --- |
| [V1 evidence](../case-resolution-evaluation-v1/README.md) | 20/20 regression observations = 10 cases repeated twice after a fix; not blind holdout |
| Same record | 3/3 narrative canary, two calls; four guarded PostgreSQL workflows; historical bounded evidence |
| Same record | 3.27 ms p95 is in-process engine timing; not API or user latency |
| [Time study](../developer-workflow-benchmark/REPORT.md) | 83.7% raw median reduction; manual 0/3 complete versus assisted 3/3; not same-outcome speedup |
| [Rollback runbook](../../runbooks/DEPLOYMENT_AND_ROLLBACK.md) | Release identity, app rollback, additive-schema/restore guidance; does not prove actual restoration |

## Capability inventory and implementation delta

Paths below are relative to repository root and name the source symbols checked.

| Capability | State | Source and delta |
| --- | --- | --- |
| Versioned brief and deterministic controls | Implemented foundation | `backend/app/analysis/deterministic_decision_engine.py`, `services/decision_brief_service.py`; expand semantic business predicates in Phases 1–3 |
| Approval snapshot and execution lease | Implemented foundation | `persistence/review_repository.py`, `persistence/actions/execution.py`, `security/review_authority.py`; prove changed policy/evidence invalidates authority |
| Verified downstream action | Partial | `persistence/actions/execution.py::finish_execution_success` assigns completed after receipt; `domain/actions.py::reconciliation_outcome_for_lookup` treats found as completed; require typed postconditions/read-back |
| Controlled closure | Missing outcome gate | `services/case_service.py::change_status`, `persistence/case_persistence/commands.py::change_status`; permission/version/transition exist, closure evidence does not |
| Reopen lifecycle | Missing | `domain/cases.py` completed has no outgoing transitions; add resolution ID, reason/time and cycle linkage |
| Operational escalation | Partial | `persistence/actions/recovery.py::escalate` assigns recovery owner and audit event; add destination routing and authorized acknowledgement receipt |
| Full semantic scorer | Missing | `evaluation/case_resolution/scoring.py::_required_action_matches` checks type/review/impact but not parameter map; escalation helper checks disposition only |
| Input/label separation | Implemented foundation | `evaluation/case_resolution/runner.py` writes observations before scoring; extend with immutable seals, family isolation and final-state grading |
| Quality counts | Partial | `persistence/quality_repository.py::_operational_summary` returns `reopened_cases=None`; `_percentage_metric` uses value 0 plus no_data on empty counts; V2 needs explicit N/A |
| Stage telemetry | Partial | Current audit/correlation and provider usage; local harness `production_validation/telemetry.py` covers capability duration, not full lifecycle spans |
| Safe automation | Not demonstrated | Review-required consequential actions remain the baseline; no eligible grant is assumed by Phase 0 |
| Dated SOP evolution | Partial | Versioned policy/retrieval foundation exists; three meaningful before/after/rollback sequences need frozen cases and proof |

## Target architecture

Keep FastAPI/PostgreSQL modular monolith, current frontend, governed retrieval, deterministic
control decisions and bounded AI narrative. Add outcome events and read-back verification around
existing action/review boundaries; PostgreSQL remains durable authority. Add routing/ack and
resolution-cycle records, then project metrics from those records. Do not equate narrative,
receipt, or status label with business proof. Introduce V2 evaluation alongside V1, not by
rewriting historical labels or reports. No payment provider is mandated by this phase.

Phase 1 must design additive migrations and old-row handling, transactionally check closure,
bind authority and operation IDs, recover uncertain effects, and handle late invalidation without
repeating the effect. Unknown legacy outcomes stay unverified. Generic manual completion must
not bypass financial verification. Phase 2 implements the scorer and actual dataset sealing;
Phase 3 proves policy changes/rollback; Phases 4–5 supply outcome/timing evidence. Packaging
and cloud validation remain Phases 6–7; final public narrative is Phase 8.
