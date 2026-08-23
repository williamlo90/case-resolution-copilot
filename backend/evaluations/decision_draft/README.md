# Phase 5 Decision And Draft Gate

Status: passed locally on 18 August 2026

This gate verifies the production Decision Brief engine and the approved draft-delivery service with
synthetic data and fake providers. It proves code-level workflow behavior without paid OpenAI calls,
Gmail access, a browser, or a local web server.

## Acceptance Matrix

| Requirement | Production boundary | Verification |
| --- | --- | --- |
| Deterministic authority | Policy state, facts, risks, outcome, actions, and approval requirements are server owned | Decision Brief runtime evaluator and deterministic engine tests |
| Bounded AI role | OpenAI can change only four narrative fields | Control-preservation and strict Pydantic output tests |
| No false completion claim | Active and passive completion claims in every narrative field fail closed | AI-assisted engine safety tests |
| Immutable approval | Review snapshot binds proposal, context, evidence, risk, and approval rule | Review service and persistence-contract tests |
| Fresh authorization | A stale approval stops before credential or provider access | Phase 5 service acceptance test |
| Bound Gmail draft | Delivery persists decision, evidence, policy, conversation, and response fingerprints | Phase 5 service acceptance and schema tests |
| Replay safety | Repeating an approved delivery creates exactly one provider draft | Phase 5 service acceptance test |
| Unknown outcome | Ambiguous create result is reconciled by lookup without replaying the write | Phase 5 service acceptance test |
| RBAC | Auditor cannot start draft delivery | Phase 5 service acceptance test |
| No automatic send | No send method or route exists | Gmail adapter and OpenAPI contract tests |

## Recorded Local Result

The bounded deterministic Decision Brief evaluator ran three production-engine control cases:

```text
cases=3 passed=3 failed=0 provider_calls=0 control_preservation=1.000
```

The focused Phase 5 verification lane passed 41 tests. The full serial backend gate then passed 388
unit/contract tests; Ruff, strict Mypy across 425 Python files, the repository secret scan, and diff
validation also passed. Runtime output is written under ignored `backend/.benchmark-data/`; no
credential or customer content is stored in this evidence directory.

## Reproduce

From `backend` with the local virtual environment active:

```powershell
python scripts/run_decision_brief_evaluation.py `
  --mode deterministic `
  --run-id phase5-local-YYYYMMDD

python -m pytest -q `
  tests/unit/test_openai_decision_engine.py `
  tests/unit/test_phase5_decision_draft_workflow.py `
  tests/unit/test_decision_brief_runtime_evaluation.py `
  tests/unit/test_review_service.py `
  tests/unit/test_inbox_persistence_contract.py `
  tests/unit/test_gmail_adapter_contract.py
```

## Evidence Limit

This is synthetic local engineering evidence. It does not prove live Gmail behavior, OpenAI model
quality, production latency, or customer impact. One bounded hosted Gmail draft journey remains an
explicit Phase 8 acceptance task after the final batch deployment.
