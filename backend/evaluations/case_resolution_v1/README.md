# Case Resolution Evaluation V1

This directory contains the frozen benchmark contract for the first automated full-decision evaluation of Case Resolution Copilot.

## Scope

- Exactly 10 synthetic cases.
- Two planned observations per case.
- Inputs and gold labels were created before product execution.
- Gold labels were reviewed against supplied evidence, governed policy text, domain rules, review authority, and action safety before execution. A separate pre-execution reviewer provenance record was not retained.
- No Case Resolution Copilot output was used to create or correct the gold labels.

The benchmark measures control-state accuracy, required source coverage, risk outcomes, escalation disposition, schema validity, action-type safety, latency, and repeat consistency. A separate bounded canary measures provider usage and cost. It does not measure semantic resolution quality or human productivity and does not replace the earlier human workflow pilot.

## Composition

| Category | Count |
| --- | ---: |
| Common | 3 |
| Missing information | 2 |
| Conflicting evidence or policy | 2 |
| Policy-heavy | 1 |
| Noisy evidence | 1 |
| Adversarial or safety | 1 |

## Files

- `inputs.json` contains only case, evidence, and governed policy inputs.
- `labels.json` contains pre-execution expected behavior and grader constraints. Its embedded review-role metadata is not treated as externally proven reviewer provenance.
- `manifest.json` freezes both files by SHA-256 and records the product revision and repeat count.
- `thresholds.json` contains explicitly provisional, not statistically validated regression checks.
- `IMPLEMENTATION_PLAN.md` records the evaluation architecture, safety controls, and remaining implementation stages.

Runtime observations and reports must be written below ignored `backend/.benchmark-data/case_resolution_v1/`. They must never overwrite these frozen files.

## Validation

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.validate_case_resolution_benchmark
```

The command validates hashes, strict schemas, exact case count, category composition, ID coverage, and all evidence/policy references. It does not run the product or call an external provider.

### Local single-case preflight

```powershell
.\.venv\Scripts\python.exe -m scripts.run_case_resolution_evaluation generate `
  --run-id local-preflight-001 `
  --case-id CRV1-001

.\.venv\Scripts\python.exe -m scripts.run_case_resolution_evaluation score `
  --run-id local-preflight-001
```

Generation reads only the frozen manifest and inputs. Scoring loads the gold labels only after observations have been persisted.

### Full deterministic run

Run the complete 20-observation suite only on isolated CI/container hardware:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_case_resolution_evaluation generate `
  --run-id deterministic-v1-full `
  --full `
  --acknowledge-isolated-run

.\.venv\Scripts\python.exe -m scripts.run_case_resolution_evaluation score `
  --run-id deterministic-v1-full
```

The acknowledgement flag prevents accidentally starting the repeated benchmark locally. It does not enable external providers.

## Results

The final post-fix regression run produced 20/20 passing observations with 100% control-state,
required evidence coverage, required policy-retrieval coverage, risk-outcome,
escalation-disposition, action-type/safety, schema, and repeat-consistency checks. A separate
provider canary passed 3/3 cases with two provider calls.
Four guarded PostgreSQL workflow scenarios also passed. See the
[sanitized evidence pack](../../../docs/evidence/case-resolution-evaluation-v1/README.md).

## Methodological Boundary

This is a small synthetic benchmark with limited statistical power. The suite exposed a conflicting-ownership defect that was fixed, so the final 100% result is regression evidence on a development set, not blind generalization evidence. Exact semantic fact phrasing, exact information-gap wording, complete action-parameter equality, and persisted review boundaries are not included in the aggregate deterministic score. A separate blind holdout is required before making a general quality claim.
