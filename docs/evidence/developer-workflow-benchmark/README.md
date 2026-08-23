# Developer-Operated Decision Readiness Benchmark

This package measures whether one developer-operator can reach a correct case disposition faster
with Case Resolution Copilot than with a reproducible manual browser workspace. It does not measure
customer impact, production-user productivity, model accuracy, or end-to-end resolution time.

The primary metric is **time to correct disposition**. A fast but unsafe or incorrect answer does
not pass.

## Current Status

- Six matched synthetic cases are defined: three Manual A variants and three Copilot B variants.
- The answer key is stored locally under `withheld/` and ignored by Git.
- `frozen-manifest.json` commits SHA-256 hashes for the public fixtures and the withheld answer key
  before any timed run is recorded.
- The manual five-view browser workspace and guarded Product B seed script are ready.
- The result sheet and report are templates only. No timed benchmark has been run and no time-saving
  claim is supported yet.

## Benchmark Lanes

**Lane A: Manual versus Copilot**

| Pair | Manual | Copilot | Decision capability |
| --- | --- | --- | --- |
| Billing | `BILL-A` | `BILL-B` | Distinguish payment attempts from a second settled charge |
| Refund | `REF-A` | `REF-B` | Apply unused-service eligibility and human approval |
| Account recovery | `ACC-A` | `ACC-B` | Block recovery on stale context and pending identity verification |

**Lane B: Safety and recovery**

Three existing deterministic tests cover stale review authority, unknown-outcome retry blocking,
and receipt reconciliation without a second execute operation. See `safety-scenarios.json`.

## Package Layout

```text
developer-workflow-benchmark/
|-- README.md
|-- PROTOCOL.md
|-- frozen-manifest.json
|-- pair-manifest.json
|-- safety-scenarios.json
|-- manual-workspace/
|   |-- index.html
|   |-- ticket.html
|   |-- customer-record.html
|   |-- business-records.html
|   |-- policy-library.html
|   |-- decision-brief.html
|   |-- cases/
|   `-- assets/
|-- product-fixtures/
|-- withheld/answer-key.json
|-- raw-results.csv
`-- REPORT.md
```

The manual workspace uses one shared renderer and case query parameters instead of duplicating 15
HTML documents. It still opens the five required browser views for each Manual A case.

## Validate Without External Services

From `backend/`:

```powershell
uv run pytest -q tests/unit/test_developer_workflow_benchmark_fixtures.py
```

This validates the six public fixtures against the real `CaseCreate` model, checks matched-pair
complexity, verifies answer leakage is absent, and confirms Lane B selectors still exist. It starts
no browser, server, database, container, or provider call.

## Run Later

Follow [PROTOCOL.md](PROTOCOL.md). Do not open `withheld/answer-key.json` until all six timed runs
are recorded. Product fixture seeding requires an explicitly approved non-production database and
is intentionally not part of local validation.

## Claim Boundary

After execution, report correctness before timing and retain this limitation:

> This developer-operated benchmark uses matched synthetic cases. It measures repeatable workflow
> performance by the product builder, not production-user productivity or customer impact.
