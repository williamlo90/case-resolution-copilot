# Phase 7 Verification And Evaluation

Status: local engineering gate passed on 19 August 2026.

This evidence covers the dirty local worktree based on commit
`d6c7de72c5636208d34e028744ac3460afc3e0fa`. It does not claim that the uncommitted revision is
already deployed. All database tests used an explicitly disposable direct Neon branch. No test
used production data, Gmail, a browser, a local web server, or parallel workers.

## Recorded Results

| Gate | Result |
| --- | --- |
| Network-free backend | `331` unit and `58` contract tests passed |
| Frontend | `160/160` tests passed; TypeScript and ESLint passed |
| PostgreSQL migration and integration | `34/34` passed on PostgreSQL `18.4` with pgvector active |
| Connected Inbox workflow | OAuth replay rejected; browse/import/sync/pause/resume/disconnect passed; imported evidence retained |
| Frozen deterministic RAG V2 | 15 cases executed; Recall@3 gate met; wrong version, unsupported citation, and cross-tenant result counts were `0` |
| Deterministic Decision Brief | `3/3` passed; safety `3/3`; control preservation `1.000` |
| Bounded live OpenAI Decision Brief | `3/3` passed; safety `3/3`; control preservation `1.000`; exactly `2/2` calls |
| Local acceptance matrix | `64` checks across `13` areas; `82` selected tests passed |
| Production workflow trace | `8` scenarios, `19` proofs, and `21` selected tests passed |
| Six-case calibration package | Six matched fixtures and answer separation validated by `9` tests |
| Static safety | Ruff passed; strict Mypy passed across `429` Python files; migration graph and secret scan passed |

## Provider Usage And Cost

The live run used synthetic inputs only. OpenAI returned complete usage metadata for both calls:

| Measure | Observed |
| --- | ---: |
| Input tokens | `1,017` |
| Cached input tokens | `0` |
| Cache-write input tokens | `0` |
| Output tokens | `278` |
| Reasoning output tokens | `0` |
| Total tokens | `1,295` |
| Total cost | `$0.000537` |
| Cost per evaluated case | `$0.000179` |
| Cost per provider call | `$0.0002685` |

Pricing was checked on 18 August 2026 against the official
[GPT-5.6 Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna): `$0.20`
input, `$0.02` cached input, and `$1.20` output per million tokens. The evaluation also recorded the
documented cache-write rate of `1.25x` regular input (`$0.25` per million), although this run used no
cache-write tokens.

The missing-policy case skipped the provider. The two provider-backed cases preserved every
server-owned fact, policy status, risk, action, approval requirement, and proposal state.

## Honest Exceptions

- The designed workflow fixture remains `7/8`: `EVAL-008` deliberately records that the first
  read-only reconciliation did not yet observe a delayed external postcondition. The executable
  production trace for safe retry blocking and read-only reconciliation passed. The fixture was not
  rewritten to manufacture a perfect score.
- The six-case package was structurally validated, but the timed one-operator comparison was not
  run. No speedup or productivity claim is supported.
- Live Gmail connect/import/replay, hosted role journeys, and warm authenticated UI LCP remain Phase
  8 gates after the batch deployment.
- This is synthetic engineering evidence, not validation on complete real client cases and not a
  production high-volume claim.

## Reproduce

From `backend/`:

```powershell
python -m pytest tests\unit -q
python -m pytest tests\contract -q
.\scripts\run_integration_tests.ps1 -ConfirmDestructiveDisposableDatabase
python -m scripts.run_local_acceptance --timeout-seconds 120
python -m scripts.run_workflow_traceability --timeout-seconds 120
python -m pytest tests\unit\test_developer_workflow_benchmark_fixtures.py -q
```

The provider run requires a configured ignored local API key and explicit pricing arguments. Do not
commit or print the key. The sanitized machine-readable summary is in `observed.json`; detailed
synthetic runtime artifacts remain under ignored `backend/.benchmark-data/`.
