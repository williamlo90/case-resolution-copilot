# Case Resolution V2 — Phase 0 contracts

This directory contains design settings and **planned, empty** split manifests, not test results.
The 40-family holdout and 12-family timing cohort will be authored/sealed in later phases.

- `measurement-contract.v1.json`: frozen measurement definitions and design targets.
- `{development,regression,holdout,time_study}.manifest.v1.json`: separate split lifecycle records.
- `*.schema.json`: generated structural schemas; Python validators also enforce cross-field rules.
- [Contract](../../../docs/evidence/case-resolution-v2/CONTRACT.md): precise business/metric semantics.
- [Baseline and architecture](../../../docs/evidence/case-resolution-v2/BASELINE_AND_ARCHITECTURE.md).
- [Claim ledger](../../../docs/evidence/case-resolution-v2/CLAIM_LEDGER.md).

Run `python -m scripts.validate_case_resolution_v2_contract` from `backend/`.
Run with `--export-schemas` only after intentionally updating a contract version/schema; this
does not seal any data. Product execution, scoring, and result reporting are Phase 2+ work.
V1 inputs, labels, evaluator and evidence remain unchanged.
