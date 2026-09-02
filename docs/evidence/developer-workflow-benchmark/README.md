# Developer-Operated Decision Readiness Benchmark

This package measures whether one developer-operator can reach a correct case disposition faster
with Case Resolution Copilot than with a reproducible manual browser workspace. It does not measure
customer impact, production-user productivity, model accuracy, or end-to-end resolution time.

The primary metric is **time to correct disposition**. A fast but unsafe or incorrect answer does
not pass.

## Current Status

- The six-case timed run is complete: three Manual A variants and three Copilot B variants.
- The answer key is stored locally under `withheld/` and ignored by Git.
- `frozen-manifest.json` commits SHA-256 hashes for the public fixtures and the withheld answer key
  before any timed run is recorded.
- The manual five-view browser workspace and guarded Product B seed script were used as defined.
- Hosted Preview preflight passed for all three Product B workspaces on revision `5d16c3a`; see
  [the sanitized preflight record](HOSTED_PREFLIGHT_2026-08-24.md).
- Final observable workflow result: Copilot `3/3`; manual `0/3`.
- Raw median elapsed time: Copilot `95 s`; manual `582 s`.
- The current Copilot state was re-read from the disposable Neon branch without exporting secrets.
- Three targeted safety and recovery tests passed in one serial Pytest process.

See [REPORT.md](REPORT.md) for interpretation and claim boundaries.

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
|-- observable-results.csv
|-- strict-diagnostic-results.csv
|-- copilot-state-snapshot.json
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

## Reproduce Final Scoring

The run is already complete. With the same disposable validation database available through
`.env.test.local`, regenerate the final local evidence from `backend/`:

```powershell
uv run python -m scripts.finalize_developer_workflow_benchmark `
  --product-commit <tested-commit> `
  --benchmark-commit <benchmark-commit> `
  --browser "Codex in-app browser" `
  --deployment "benchmark-validation Vercel preview" `
  --seed-target "approved-non-production-branch"
```

This regenerates `observable-results.csv`, `copilot-state-snapshot.json`, and `REPORT.md`. The
original exact-ID scorer output remains as `strict-diagnostic-results.csv`; it is an
instrumentation diagnostic, not the final workflow result.

## Final Scoring Contract

- Evidence uses source references visible to an operator, such as invoice and payment references.
- UI labels are normalized to their canonical safe actions.
- Approval checks the human-review boundary; the active settings may route a case to a stronger
  reviewer role.
- Copilot results must also match the state persisted in the disposable database.
- Unsupported consequential claims or unsafe execution attempts fail a case.

## Claim Boundary

Report correctness before timing and retain this limitation:

> This developer-operated benchmark uses matched synthetic cases. It measures repeatable workflow
> performance by the product builder, not production-user productivity or customer impact.
