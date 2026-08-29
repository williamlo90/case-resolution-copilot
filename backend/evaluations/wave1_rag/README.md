# Wave 1 Credential-Free RAG Evaluation

This bounded evaluation exercises the production `V2PolicyRetrieval` resolver with a deterministic,
in-memory adapter. It needs no database, Redis, OpenAI key, Gmail connection, browser, or network.

The synthetic fixture covers duplicate billing, refund eligibility, account recovery, service
exceptions, privacy handling, missing policy coverage, and an incomplete index. Expected clause
sources are stored with each case and checked against the top three returned citations.

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_wave1_rag_evaluation `
  --require-gate `
  --output .benchmark-data\wave1_rag\report.json `
  --events .benchmark-data\wave1_rag\events.jsonl
```

The command reports source hit rate, source recall, status accuracy, p50/p95 retrieval latency, and
case-level failures. Structured events contain case IDs, returned source IDs, status, latency, and a
bounded exception type only. They intentionally exclude query text, source content, customer data,
credentials, and exception messages.

This is deterministic component-level evidence for retrieval orchestration and scoring. It is not a
claim about PostgreSQL/pgvector query plans, hosted latency, OpenAI embedding quality, production
scale, or real-client outcomes. The database-backed retrieval V2 benchmark remains the integration
check for those repository boundaries.
