# Product B Fixtures

Each JSON file contains a `case` object that validates against the backend `CaseCreate` model, plus
seven additional conversation messages and the governed policy IDs used in the benchmark.

The fixtures are not loaded by normal application startup. The guarded non-production seeder is:

```powershell
cd backend
$env:SUPPORT_COPILOT_ALLOW_BENCHMARK_SEED="1"
uv run python -m scripts.seed_policies
uv run python -m scripts.seed_developer_workflow_benchmark
```

The script is additive and idempotent by public ID. It refuses production, requires a database URL,
requires explicit opt-in, verifies the four governed policies already exist, and never deletes or
updates unrelated cases.
