# Test targets and execution boundary

## Phase 0 gate (implemented here)

`backend/tests/unit/test_case_resolution_v2_contracts.py` validates frozen measurement settings,
exported JSON schemas, planned manifests, required metric definitions, policy dates, contradictory
authority/action/oracle records, distinct split families, seal requirements, denominators, and
same-outcome pair eligibility. Examples used by tests are development schema examples only.
No benchmark corpus or product score is generated.

Run from `backend/` with the repository Python 3.12 environment:

```text
python -m pytest tests/unit/test_case_resolution_v2_contracts.py -q
python -m scripts.validate_case_resolution_v2_contract
python -m ruff check app/evaluation/case_resolution_v2 scripts/validate_case_resolution_v2_contract.py tests/unit/test_case_resolution_v2_contracts.py
python -m mypy app/evaluation/case_resolution_v2 scripts/validate_case_resolution_v2_contract.py tests/unit/test_case_resolution_v2_contracts.py
```

No database, browser, container, model provider, cloud or full evaluation is needed.

## Phase 2 gate (implemented)

The separate V2 scorer, runner, dataset and mutation checks are described in
[EVALUATOR.md](EVALUATOR.md) and the [Phase 2 checkpoint](../../learning/case-resolution-v2/PHASE-2.md).
Run the three `test_case_resolution_v2_{contracts,scoring,runner}.py` unit modules, the existing
contract validator, and `python -m scripts.evaluate_case_resolution_v2 validate-corpus`.
These are bounded evaluator/static checks. No holdout product run is performed.

## Phase roadmap (execution status in each checkpoint)

Phase 3 source and instructions: [SOP revisions](SOP_REVISIONS.md),
[learning checkpoint](../../learning/case-resolution-v2/PHASE-3.md), and
[operator runbook](../../runbooks/sop-change-and-recovery.md).
Local unit module: `tests/unit/test_sop_revision_decisions.py`.
Guarded PostgreSQL module: `tests/integration/test_sop_revision_lifecycle.py` (race test skips locally).
The `SOP revision gate` workflow runs the complete exposed replay and race test in isolation,
with report and JUnit artifacts bound to the exact commit. No Phase 2 holdout observation is generated.

| Phase | Required tests |
| --- | --- |
| 1 | Completion/reopen transition and prior-cycle attribution; migration legacy rows; cross-tenant/permission denial; stale review; fail-after-effect; read-back mismatch; routing+ack receipt; missing telemetry; bounded PostgreSQL journey |
| 2 | Mutate amount/currency/recipient/target/tenant/policy dates and missing facts/gaps; extra consequential parameter; schema-valid wrong outcome; frozen hash tampering; runtime cannot read labels; corpus tag counts and semantic family review |
| 3 | Effective-date boundaries; meaningful before/after decisions for three revisions; approval invalidation; rollback/resume without duplicate effect; real captured development failure promoted to regression |
| 4 | Frozen candidate lifecycle holdout; all scheduled failures counted; final read-back; cost/usage completeness; stage timing; safe automation eligibility and actual exception routing |
| 5 | Separate cohort seal; balanced order; same oracle both conditions; incomplete manual work excluded from time numerator but retained in completion denominator; raw pair reconciliation |
| 6 | Reproducible demo/package; migration/security scans; bounded restore/rollback and restart recovery |
| 7 | Cloud-only workload/cost/teardown gates, bounded concurrency/queue/DLQ/soak and provider canary, no critical/high image blocker |
| 8 | Evidence links/reproduction and exact claim/denominator audit |

Local resource policy remains authoritative. Full corpus/replay loops, local browser E2E and load
tests are not authorized by this test list. Run heavy work in the approved isolated environment.
