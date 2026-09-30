# Case Resolution Evaluation V1

This evidence pack records three bounded validation lanes executed on 2026-09-30. The lanes answer different questions and are not combined into one inflated score.

## Results

| Lane | Result | What it proves |
| --- | ---: | --- |
| Deterministic regression | 20/20 observations passed across 10 synthetic cases and two repeats | Control-state accuracy, required evidence and policy-retrieval coverage, risk outcomes, escalation disposition, action-type safety, schema validity, and repeat consistency |
| OpenAI narrative canary | 3/3 cases passed; 2 provider calls; `$0.001077` total measured cost | Optional narrative generation preserved deterministic controls and correctly skipped the provider when policy was missing |
| Persisted workflow | 4/4 guarded PostgreSQL scenarios passed | Conflict blocking, immutable approval snapshots, exactly-once controlled execution, and unknown-outcome reconciliation |

The deterministic run recorded `1.89 ms` P50 and `3.27 ms` P95 for the in-process decision engine. These are engine timings, not API latency or human productivity evidence.

## Method

- Inputs and reviewed gold labels were frozen with SHA-256 hashes before the first run. A separate pre-execution reviewer-provenance artifact was not retained.
- The product generated input-only observations; the scorer loaded labels afterward.
- The final deterministic run was rescored after a product defect was found and fixed.
- The provider canary had a hard ceiling of two provider calls, no SDK retries, complete token usage, and current pricing metadata.
- Database scenarios ran through the guarded integration script against a migrated PostgreSQL branch.

## Claim Boundary

The appropriate public statement is:

> A 20-execution synthetic regression suite passed all implemented control-state, required-source coverage, risk, escalation-disposition, action-type/safety, schema, and consistency checks. A separate two-call OpenAI canary preserved controls in 3/3 cases, and four guarded PostgreSQL scenarios validated critical review and action paths.

This is not a blind holdout, customer-impact study, production load test, or proof of general accuracy. The suite became a development set after it exposed a conflicting-ownership defect. See [METHODOLOGY_AUDIT.md](METHODOLOGY_AUDIT.md) for the detailed limits.

## Artifacts

- [Deterministic aggregate](deterministic-regression-results.json)
- [Provider canary aggregate](provider-canary-results.json)
- [Persisted workflow aggregate](persisted-workflow-results.json)
- [Methodology audit](METHODOLOGY_AUDIT.md)
- [Frozen benchmark contract](../../../backend/evaluations/case_resolution_v1/README.md)

Raw runtime artifacts remain ignored under `backend/.benchmark-data/` so the public repository contains concise, sanitized evidence rather than provider-generated narratives or transient execution files.
