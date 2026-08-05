# Pilot SLO Evaluation

Status: Application instrumentation, bounded evaluator, and provisional pilot objectives are
implemented; production observation evidence is pending a structured Vercel log export.

## Objectives

`backend/operations/pilot_slo.json` defines a seven-day pilot observation:

| Objective | Target |
| --- | ---: |
| HTTP availability, counting non-5xx responses as available | at least `99.5%` |
| Application request latency p95 | at most `1500 ms` |
| Minimum eligible sample | `100` requests |

Liveness and readiness probes are excluded so infrastructure polling cannot inflate application
traffic results. These are provisional pilot objectives, not contractual enterprise SLOs.

## Input Contract

The backend already emits one JSON event after every request:

```json
{
  "timestamp": "2026-07-29T00:00:00+00:00",
  "logger": "app.api.middleware",
  "message": "request_completed",
  "method": "GET",
  "path": "/api/cases",
  "status_code": 200,
  "duration_ms": 125.5
}
```

Export backend application logs from Vercel as newline-delimited JSON. Do not include deployment
environment variables or secret-manager output. The evaluator ignores unrelated JSON events and
fails on malformed request events.

## Evaluation

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_pilot_slo `
  --logs C:\path\to\vercel-request-logs.jsonl
```

Optional reproducible window end:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_pilot_slo `
  --logs C:\path\to\vercel-request-logs.jsonl `
  --as-of 2026-07-29T23:59:59+07:00
```

The default report is written to `.codex-runtime/pilot-slo-report.json` and a sibling Markdown
file. Both are ignored by Git.

Exit codes:

- `0`: both objectives passed with enough data;
- `1`: at least one objective failed;
- `2`: fewer than the required eligible requests were present.

## Safety And Privacy

- Input is limited to 50 MiB and 250,000 eligible request events.
- Evaluation is single-process and streaming at the file boundary.
- Reports contain only aggregate counts, availability, latency p95, timestamps, and the source file
  hash.
- Request paths, correlation IDs, headers, payloads, and customer data are never copied into the
  report.
- A passing report does not prove alert delivery, paging ownership, provider health, or incident
  response.

## Activation Gate

Production telemetry remains incomplete until:

1. Vercel log retention or an approved external log destination is active.
2. A seven-day export is evaluated with at least 100 eligible requests.
3. Failed objectives have an owner and alert route.
4. The observation and incident process are repeated after material deployment changes.
