# Product B Fixtures

Each JSON file contains a `case` object that validates against the backend `CaseCreate` model, plus
seven additional conversation messages and the governed policy IDs used in the benchmark.

The fixtures are not loaded by normal application startup. The guarded non-production seeder is:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.prepare_developer_workflow_benchmark `
  --confirm-disposable-database
```

The wrapper requires `TEST_DATABASE_SCOPE=disposable`, verifies that the declared endpoint ID
matches a direct TLS Neon URL, applies pending Alembic migrations, and requires explicit
confirmation. Seeding is additive and idempotent by public ID. It never deletes or updates
unrelated cases. On a fresh branch it first creates the deterministic benchmark organization and
role set required by the fixtures.
