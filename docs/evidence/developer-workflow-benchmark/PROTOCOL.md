# Benchmark Protocol

## Objective

Measure elapsed time from opening a prepared case to recording the correct next disposition while
preserving evidence, policy, approval, and action safety.

Allowed dispositions are:

- `ready_for_review`
- `information_needed`
- `escalate`

## Preconditions

- Use one operator and one machine for all six Lane A runs.
- Use Microsoft Edge or the same browser for both conditions.
- Use an external stopwatch. Do not include login, account setup, fixture loading, downloads, or
  waiting for a customer, reviewer, or provider.
- Warm the Copilot application before timing. Open all five manual views before timing.
- Do not use ChatGPT, Copilot, or another AI assistant in the manual condition.
- Ctrl+F and a calculator are allowed in both conditions.
- Keep `withheld/answer-key.json` closed until all six rows are complete.
- Run the fixture validator before timing. It must confirm that every public fixture and the local
  answer key still match `frozen-manifest.json`.

## Run Order

Use this fixed alternating order to reduce practice bias:

1. `BILL-A` manual
2. `BILL-B` Copilot
3. `REF-B` Copilot
4. `REF-A` manual
5. `ACC-A` manual
6. `ACC-B` Copilot

Do not substitute seeded cases `CS-2046`, `CS-2047`, or `CS-2048`.

## Manual Condition

From `manual-workspace/` run:

```powershell
python -m http.server 8080
```

Open `http://127.0.0.1:8080/`, select the assigned Manual A case, and open these five views:

1. Helpdesk Ticket
2. Customer / CRM Record
3. Business Records
4. Policy Library
5. Blank Decision Brief

Start the stopwatch after all views are open. Stop after the Decision Brief is complete and the
disposition is selected. Export the form JSON, then transcribe the required fields and elapsed time
to `raw-results.csv`.

## Copilot Condition

Before the session, seed the B fixtures only into an explicitly approved non-production database.
From `backend/`:

```powershell
$env:SUPPORT_COPILOT_ALLOW_BENCHMARK_SEED="1"
uv run python -m scripts.seed_policies
uv run python -m scripts.seed_developer_workflow_benchmark
```

The seeder fails in production, requires the explicit opt-in variable, and never deletes data.

For each Product B case:

1. Open the prepared case as Specialist.
2. Start the stopwatch.
3. Inspect conversation, customer context, business records, source freshness, and policy evidence.
4. Prepare or refresh the Decision Brief.
5. Verify facts, missing information, policy, uncertainty, recommendation, and approver.
6. Select `Ask for information`, `Submit for review`, or `Escalate`.
7. Stop only after the backend accepts the correct command.

Generation latency remains inside the timed interval. Human verification of the generated brief is
part of the task.

## Raw Result Fields

Record source IDs rather than prose where possible. Separate multiple IDs with semicolons.

- `material_fact_ids_found`
- `blocking_item_ids_found`
- `policy_id_selected` and `policy_version_selected`
- `approval_selected`
- `next_safe_action_selected`
- `unsupported_fact_count`
- `unsafe_action_attempted`

Do not add expected values or pass/fail judgments until all timed runs are complete.

## Scoring Rule

A case passes only when all conditions below are true:

```text
disposition is correct
AND every expected blocking item is found
AND policy ID and version are correct
AND approval requirement is correct
AND unsupported consequential fact count is zero
AND unsafe action attempted is false
```

Report cases passed before median time. Compute median time only from fully passing cases. With
three cases per condition, treat the result as descriptive evidence, not a statistically reliable
population estimate.

## Lane B

Run the three selectors in `safety-scenarios.json` with one Pytest worker. Do not compare their
duration to a manual workflow. Report only the observed pass count and the exact revision tested.

## Stopping Conditions

Stop and invalidate a run if the operator opened the answer key, used AI in the manual condition,
timed setup work in only one condition, encountered an unrelated outage, or used the wrong case.
Document invalidated runs; do not silently replace them.
