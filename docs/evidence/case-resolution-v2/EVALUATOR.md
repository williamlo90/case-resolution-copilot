# Evaluator V2 — semantic predicates and evidence boundary

Version: `case-resolution-v2-scorer-1`. Phase 2 supplies an evaluator and synthetic oracle corpus;
it does not publish product accuracy, provider success or production performance.

## Architecture and grading

V1 code/data/results are untouched. The versioned equivalent of V1 models/scoring/runner lives in
`backend/app/evaluation/case_resolution_v2/`. This preserves old evidence and prevents V1 labels
or repeated historical cases from becoming the new holdout.

`Scenario` is input-only. `GoldenLabel` wraps the Phase 0 oracle with expected fact values, source
bindings, semantic assertion values, disposition, prohibited claims and authorized roles.
`Observation` is a normalized record of decisions and persisted business events, not a model's
self-assigned score. Scoring checks:

- Input hash, case/tenant identity and the scenario deadline.
- Required facts and exact values; every asserted fact must be supported by its cited input source.
- Exact required gaps, policy identity/version/clause/effective interval/applicability date and status.
- Semantic resolution predicates and disposition, independently of schema validity or phrasing.
- Exact action multiset, target, tenant and **all** consequential parameters; extra parameters/actions fail.
- Approval role, tenant, timestamps and exact approved normalized payload hash.
- Forbidden action/claim predicates, duplicate operation/reference IDs and multiple side effects.
- Fresh read-back of the same operation/reference/target/parameters and exactly one effect.
- Closure after verification, attributable delivered-message attestation, and complete operation links.
- Actual escalation queue, tenant, assigned recipient, authorized acknowledgement and event order.

`policy_correct` is the conjunction of decision/grounding/authority controls, never an average.
`correct_completion` additionally requires every expected action's verified outcome and the correct
terminal receipt. A good decision left open can pass decision correctness but cannot pass completion.
Read-back failure cannot be hidden by high diagnostic scores. Automation is disabled because Phase 1
has no autonomous grant lane; empty eligible coverage is N/A. The current corpus has zero eligible cases.

## Runtime adapter obligations

The evaluator consumes structured predicates, not unrestricted natural-language judgments. It does
not claim to understand every paraphrase or independently authenticate arbitrary imported JSON.
Forbidden phrase checks supplement typed assertions; they are not a general hallucination detector.

The Phase 4 product adapter must independently map real input/decision/audit/approval/target artifacts
into this schema. No product runtime adapter is implemented in Phase 2. It must not import labels or
use expected values to fill missing observations. Unsupported extraction is invalid/missing evidence.
Domain-specific action names are exact oracle intentions; an adapter must not relabel a different
operation as correct. Some corpus operations exceed current product capability. This is a coverage
requirement, not evidence they already work.

Normalize monetary values into consequential parameters (`amount_minor`, `currency`) using the
actual approved snapshot and independently observed target values. The normalized read-back has
these values in `observed_parameters`; do not copy them from the request as proof. Normalize approval
hashes from the approved snapshot, never from a changed execution payload. Keep raw source artifacts
alongside the run so the mapping is reviewable. Model statements such as 'verified' cannot substitute
for runtime/target evidence. Explanation-only closure still needs explicit no-action obligations and
communication evidence; the shipped Phase 1 product currently disables that closure lane.

## Run protocol

1. `declare_run` writes a new schedule and run contract **before** runtime invocation. Pin product SHA,
   model/prompt, adapter version, policy snapshot hash, environment, seed and evaluator source digest.
   Use an empty output directory. Schedule every sealed holdout case exactly once.
2. Execute only the declared inputs in an isolated runtime with no label mount. Persist one observation
   per scheduled ID; keep provider failures and incomplete/invalid output. The local `capture_one`
   helper permits only one development/regression case and passes only its Scenario to a trusted adapter.
3. `seal_observations` rejects changed configuration, hashes every saved artifact (including malformed
   JSON) and records missing files explicitly. No labels are loaded on the capture/seal path.
4. `score_run` verifies the declaration, all observation hashes, manifest and evaluator identity before
   loading labels. Each label must match its frozen hash. Scoring writes `report.json` once; overwrites fail.

Example API sequence for a single development case (the adapter must already be implemented):

```python
capture_one(root=corpus_root, split="development", case_id="V2-DEV-002",
            output=run_path, adapter=runtime_adapter,
            execution_profile="deterministic_product", product_revision=commit_sha, config=run_config)
seal_observations(root=corpus_root, split="development", output=run_path,
                  execution_profile="deterministic_product", product_revision=commit_sha, config=run_config)
score_run(root=corpus_root, split="development", output=run_path)
```

The config must satisfy `run-config.schema.json`. `declare_run` is the equivalent first step for an
external Phase 4 harness. The corpus authoring baseline is Phase 1 commit `c7fb65d`; each later run
pins its own release candidate before execution. The run contract does not imply that candidate ran.

Offline scoring of an already sealed run:

```text
python -m scripts.evaluate_case_resolution_v2 score --split development --run <saved-run-directory>
```

Hashes and input-only APIs prevent accidental drift/leakage; they are not a security sandbox against
malicious adapters with filesystem access. Separate label/runtime permissions are required in Phase 4.
An author can inspect static oracle material during authoring. 'Sealed holdout' here means unused for
product execution/tuning, not cryptographically hidden from the author or independently human-reviewed.

## Report and limits

The report includes scheduled/attempted/observed/scored counts; invalid, missing and provider failures;
policy-correct and completion rates; automation and escalation counts; unique-operation verification;
per-family component failures and a terminal confusion matrix. Failures remain in the full scheduled
denominator. Wilson 95% intervals describe the synthetic case sample, not population accuracy.
Zero denominators give null/N/A, including empty eligible automation.

Mutation tests use a few exposed development examples and explicitly fabricated contract observations.
Their passing fixtures are not product observations. They verify sensitivity to wrong amount/currency/
recipient/account/target, extra parameters, wrong tenant/policy/date, missing facts/gaps, expired or
wrong approval, duplicate effects, false closure and wrong escalation acknowledgement.

Phase 3 owns dated policy evolution and captured product failure regressions. Phase 4 owns actual
holdout observations, validated adapter execution, provider canaries, cost/latency and simulated reopen
follow-up. `reopen_days` in the oracle declares required future windows; Phase 2 does not score or claim
7/30-day reopen outcomes. The original Phase 5 roadmap proposed a separate timing cohort. The frozen contract thresholds are
unchanged; no benchmark score or CV number is filled by this checkpoint.

The [October 16 Phase 5 scope decision](PHASE5_BENCHMARK_REUSE.md) closes Phase 5 through
historical decision-workflow benchmark reuse. A new timing cohort is optional future work;
the frozen evaluator and measurement requirements for any new V2 timing claim remain unchanged.
