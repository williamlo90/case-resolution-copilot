# Phase 6 OpenAI Activation Evidence

Status: passed locally on 18 August 2026

This gate verifies that the configured OpenAI project key can call the production narrative model
through the Responses API. It uses only synthetic Decision Brief controls and makes no Gmail,
browser, database, or customer-data request.

## Preflight

- The backend detected a usable API key without printing or persisting its value.
- Safe logging omitted the API-key field.
- The configured model was `gpt-5.6-luna` with a 12-second request timeout.
- The canary disabled SDK retries and enforced a hard ceiling of two provider calls.
- The gateway caps narrative input at 24,000 characters and output at 1,200 tokens.
- [Official OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
  listed the Responses API and structured outputs as supported at activation time.

## Observed Canary

| Measure | Result |
| --- | ---: |
| Synthetic cases | `3` |
| Passed | `3/3` |
| Provider calls | `2/2` maximum |
| Structured schema valid | `3/3` |
| Safety boundary passed | `3/3` |
| Deterministic control preservation | `1.000` |
| Model modes | `ai_assisted`, `ai_assisted`, `skipped` |

The missing-policy case skipped OpenAI by design. The other two cases used AI-assisted wording while
keeping server-owned facts, policy status, risks, actions, approval requirements, and proposal state
unchanged.

The sanitized machine-readable result is in [`observed.json`](observed.json). Detailed runtime
artifacts remain under ignored `backend/.benchmark-data/` and contain synthetic inputs only.

## Network-Free Regression

After the canary, 46 focused configuration, provider-wiring, structured-output, fallback, evaluator,
input-limit, and secret-scan tests passed without further provider calls. The explicit input ceiling
was added and verified offline after the live canary; no extra paid request was made for that
fail-before-provider guard.

The final serial backend gate passed 389 unit/contract tests. Ruff, strict Mypy across 425 Python
files, JSON validation, the repository secret scan, and diff validation also passed.

## Activation Decision

The local and hosted runtime default remains `deterministic`. This is deliberate: verification,
local startup, and background work must not spend API credit accidentally. The OpenAI provider is
enabled by changing the backend-only `SUPPORT_COPILOT_MODEL_PROVIDER` setting at the controlled
Phase 8 deployment gate.

## Evidence Limit

This result proves API access, model availability for this project, schema compatibility, and the
Decision Brief control boundary at one point in time. It does not prove production latency, daily
availability, Gmail integration, customer impact, or cost per case. OpenAI project budget settings
are user-managed and were reported configured but were not read or independently verified. Phase 7
subsequently recorded complete provider usage and cost per evaluated case in
[`../phase7_verification`](../phase7_verification/README.md).
