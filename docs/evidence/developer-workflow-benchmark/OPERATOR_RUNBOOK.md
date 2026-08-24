# Six-Case Operator Runbook

This is the shortest valid path through the benchmark. The operator performs the timed work; Codex
prepares fixtures, checks the environment, and scores the completed sheet afterward.

## Before Timing

1. Do not open `withheld/answer-key.json`.
2. Use one browser, one laptop, one operator alias, and one external stopwatch for all six cases.
3. Ask Codex to validate the fixtures and seed `CS-BENCH-BILL-B`, `CS-BENCH-REF-B`, and
   `CS-BENCH-ACC-B` into the disposable Neon branch in `backend/.env.test.local`.
4. Open `raw-results.csv` in Excel and fill one `run_date` and one non-sensitive `operator_id` in
   all six prepared rows.
5. Warm both workspaces before timing. Setup and login time are excluded.

If preparation reports a database connection failure, replace only `TEST_DATABASE_URL` in the
ignored `backend/.env.test.local` with a fresh direct connection string from the same disposable
Neon branch. Never paste that URL into chat or commit it.

## Manual Workspace

From `manual-workspace/`, run:

```powershell
.\serve.ps1
```

Open `http://127.0.0.1:8080/`. The server is a small static Python process; stop it with `Ctrl+C`
after all three manual cases are complete.

For a manual case, open its five views before starting the stopwatch. Stop after the blank Decision
Brief is complete and a disposition is selected. Export the JSON, then record the IDs and elapsed
seconds in the matching CSV row.

## Copilot Workspace

Use the deployed app while signed in as Specialist:

- `/cases/CS-BENCH-BILL-B`
- `/cases/CS-BENCH-REF-B`
- `/cases/CS-BENCH-ACC-B`

Start the stopwatch after the prepared case opens. Inspect the evidence and policy, prepare or
refresh the brief, verify it, and choose the next safe workflow action. Stop when the backend
accepts that action. Record the result immediately.

## Fixed Order

1. `BILL-A` manual
2. `BILL-B` Copilot
3. `REF-B` Copilot
4. `REF-A` manual
5. `ACC-A` manual
6. `ACC-B` Copilot

## After All Six Rows

Tell Codex that the six rows are complete. Codex will run the scorer, inspect correctness before
timing, execute the three deterministic safety checks, and produce `scored-results.csv` plus the
final `REPORT.md`.

Do not describe this as real-client impact. It is a matched synthetic, single-operator workflow
benchmark.
