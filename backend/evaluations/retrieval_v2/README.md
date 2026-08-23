# Frozen Governed RAG V2 Benchmark

Status: Phase 4 retrieval gate passed on 2026-08-15.

This answer-separated benchmark evaluates the same synthetic queries and metadata against:

- deterministic RAG V1;
- deterministic hybrid RAG V2;
- OpenAI `text-embedding-3-small` hybrid RAG V2.

The input and label files are separately hash-locked by `manifest.json`. Retrieval receives only the
input case. Scoring loads the labels after each observation has been produced.

## Dataset

- 15 total cases.
- 8 relevant queries covering every clause in the four-policy governed corpus.
- 2 release-corpus negatives covering stale policy and cross-tenant denial.
- 5 frozen guard-contract negatives covering missing, inapplicable, stale, conflicting, and
  incomplete-index states.
- All content is synthetic and contains no Gmail or customer data.

The release-corpus lane queries the configured Neon PostgreSQL repository. Guard-contract lanes
exercise the real V1/V2 resolution guards with frozen scope counts; they do not claim to be
PostgreSQL integration evidence. The cross-tenant release case calls the real repository with an
unknown organization and must return no clause.

## Observed Result

| Profile | Recall@3 | MRR | Status accuracy | Embedding calls | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| Deterministic V1 | 1.000 | 1.000 | 1.000 | 15 | 138.056 ms | 562.427 ms |
| Deterministic V2 | 1.000 | 1.000 | 1.000 | 8 | 415.960 ms | 582.113 ms |
| OpenAI V2 | 1.000 | 1.000 | 1.000 | 8 | 823.374 ms | 5536.589 ms |

All three runs recorded:

- wrong policy version: 0;
- unsupported citation: 0;
- cross-tenant result: 0;
- irrelevant near-match at rank 1: 0;
- failure-state classification accuracy: 1.000.

The complete sanitized observations are in `observed.json`. OpenAI latency is provider-backed
retrieval latency, not browser or UI performance.

## Run

Credential-free V1 and deterministic V2:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_retrieval_v2_benchmark
```

One bounded OpenAI pass and an enforced Phase 4 gate:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_retrieval_v2_benchmark `
  --include-openai `
  --require-phase4-gate `
  --output evaluations\retrieval_v2\observed.json
```

The OpenAI run makes eight serial embedding calls over synthetic queries. It does not invoke a
narrative model, Gmail, a browser, or parallel workers.

## Claim Boundary

This benchmark proves retrieval behavior for a small synthetic four-policy corpus in the configured
development environment. It does not prove production scale, real-client quality, hosted Gmail
behavior, or UI latency. OpenAI V2 remains disabled in production until its activation and rollback
gates are completed.
