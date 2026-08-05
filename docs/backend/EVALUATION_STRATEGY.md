# Evaluation Strategy

## What Is Being Evaluated

Case Resolution Copilot has three distinct quality surfaces. They must not be collapsed into one
accuracy number.

1. **Decision quality** checks whether a brief identifies supported facts, missing information,
   applicable policies, risks, approval requirements, and a defensible recommendation.
2. **Workflow safety** checks whether review, approval, action execution, duplicate protection, and
   recovery follow the expected state transitions.
3. **Operational reliability** checks whether the system remains available, traceable, and within
   agreed pilot thresholds.

## Evaluation Layers

### Deterministic fixtures

Small local fixtures exercise decision generation without network credentials. They are fast enough
for every local quality gate and make regressions reproducible.

### Workflow golden cases

The workflow evaluator compares observed transitions with a versioned golden specification. It
verifies behavior such as required approvals, immutable review decisions, idempotent action
execution, and recovery from an unknown provider outcome.

### Public benchmark

The public benchmark pipeline transforms externally sourced support-like records into a documented
evaluation format. `backend/benchmarks/public/sources.json` records provenance and the benchmark
README states the limits of the data. This evidence measures the transformation and scoring system;
it is not a substitute for validation on complete real client cases.

### Controlled pilot scorecard

The templates under `docs/pilot/templates` separate evidence available to the application from the
historical outcome used by an evaluator. They support calibration, blinded validation, timing, and
supervisor traceability without requiring production-system access.

## Reproducibility Rules

- Inputs, expected outcomes, evaluator versions, and observed results are separate artifacts.
- A generated observation must record the code revision and fixture digest that produced it.
- Historical decisions are comparison data, not an automatic source of truth.
- Missing evidence is represented explicitly instead of being silently treated as a negative fact.
- Deterministic and model-backed runs are reported separately.
- A test that requires credentials or an external database must skip with a clear reason.

## Quality Dashboard

The dashboard is a projection over persisted evaluation evidence. It is read-only for operational
users and tenant-scoped through the same authorization boundary as the rest of the application.
It shows pass, warning, and fail evidence by category; it does not allow an operator to rewrite an
evaluation outcome from the UI.

## Claims This Milestone Supports

- The repository contains repeatable local decision and workflow evaluators.
- Evaluation inputs and benchmark provenance are versioned.
- Quality evidence can be persisted and inspected through the product UI.
- Controlled-pilot templates define how future client validation should be recorded.

## Claims This Milestone Does Not Support

- Production readiness at high volume.
- General model accuracy across industries.
- Validation on complete real business cases.
- A guarantee that a public benchmark predicts pilot performance.

Those claims require representative external data, independently reviewed outcomes, and hosted
operational measurements.
