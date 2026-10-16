# Case Resolution V2 corpus and evaluator

Phase 2 contains **authored synthetic scenarios, not product evaluation results**.

| Split | Families | Status |
| --- | ---: | --- |
| Development | 24 | Exposed; iteration allowed |
| Regression V2 | 3 | Exposed; evaluator regression examples, not captured product incidents |
| Holdout | 40 | Sealed before product execution; 14 billing / 13 refund / 13 account recovery |
| Time study | 0 | Planned; the separate 12-family cohort belongs to Phase 5 |

Historical V1 remains a separate regression reference (`legacy-regression-reference.v1.json`).
The V2 holdout contains 36 critical-tagged cases, with four cases for each cross-cutting risk tag.
Family and SOP-family identities are disjoint across splits. Operative business rules differ;
changing only amounts or IDs does not constitute a new family. Static validation checks identity,
exact/normalized rule duplication, domain/tag counts, grounded facts, policy references and hashes.
Semantic family review is recorded in `adjudication.v1.json`; it is an agent review, not an
independent human assessment or a guarantee of complete semantic deduplication.

Inputs and labels were authored from synthetic source rules before seeing product outputs.
Provenance is `ai_authored_agent_adjudicated`. No independent human review is claimed. This explicit
provenance value extends the Phase 0 oracle schema without changing measurement thresholds.
Business-rule families intentionally probe capabilities beyond the current deterministic engine;
no pass rate is promised. Unsupported operations must fail or safely escalate, never be silently
aliased to a different operation to improve the score. Runtime coverage must be developed and
validated on development cases before Phase 4; do not tune the product on these holdout labels.

- `measurement-contract.v1.json` and its checksum: unchanged Phase 0 measurement contract.
- Split manifests: per-case canonical input/label SHA-256, family identities, seed, authoring baseline,
  model/prompt configuration and scorer version. The suite config pins the evaluator source digest.
- `*/inputs/*.json`: request, tenant, evidence, source policies, risk conditions and simulated deadline.
- `*/labels/*.json`: expected facts/gaps, source bindings, semantic predicates, exact actions,
  escalation/terminal requirements and rationale.
- `*.schema.json`: exported contracts, including normalized observations and run configuration.
- [Evaluator guide](../../../docs/evidence/case-resolution-v2/EVALUATOR.md).
- [Learning checkpoint](../../../docs/learning/case-resolution-v2/PHASE-2.md).

Safe static validation from `backend/`:

```text
python -m scripts.validate_case_resolution_v2_contract
python -m scripts.evaluate_case_resolution_v2 validate-corpus
```

These commands validate data and schemas; they do not invoke an engine, model, database or provider.
Holdout authoring/static checks do not count as evaluation. If used for product debugging, demote the
exposed families and create a replacement holdout before a final run. A hash seal is a reproducibility
control, not encryption or protection against an owner deliberately changing files.
