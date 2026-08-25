# Phase 8 operational readiness - 2026-08-25

## Verdict

The current system passed the operational-readiness gate for a controlled pilot. The evidence
combines one bounded hosted Gmail journey with disposable-database integration tests and
deterministic provider fault injection. It does not claim general production readiness, arbitrary
scale, or measured customer impact.

## Verification results

| Gate | Result | Evidence |
| --- | --- | --- |
| Migration graph | Pass | One base, one head (`20260813_0024`), 24 revisions |
| Disposable Neon connection | Pass | Direct TLS connection, PostgreSQL 18.6, pgvector active |
| Connected inbox lifecycle | Pass | Connect, import, import replay, sync replay, pause, resume, disconnect, reconnect, and retained case history |
| Inbox lifecycle audit | Pass | Two connect events plus pause, resume, disconnect, and reconnect correlation records |
| Provider side-effect recovery | Pass | Duplicate key, pre-send timeout, post-acceptance timeout reconciliation, and delayed postcondition |
| Operational controls | Pass | Tenant-scoped settings, notifications, member safeguards, and audit export |
| Backend fault matrix | Pass | 73 unit/contract checks covering auth failure, provider outage, timeout, stale approval, duplicate draft prevention, and unknown-outcome reconciliation |
| PostgreSQL operational checks | Pass | 3 focused integration checks across the connected workflow and operational API |
| Provider simulator | Pass | 4 deterministic failure and replay scenarios |
| Frontend recovery states | Pass | 35 checks across expiry, reconnect-required, rate limit, timeout, cancellation, and unknown draft outcome |
| Hosted authenticated readiness | Pass | Warm reload to visible `Cases` primary heading in 375 ms against a 2,500 ms gate; no runtime errors |
| Hosted connected draft journey | Pass | One synthetic Gmail thread reached an approved, persisted Gmail draft without automatic send |
| Timed operator benchmark | Pass | Copilot produced 3/3 complete safe outcomes versus 0/3 manually; raw medians 95 s and 582 s |

## Failure-path boundary

Live Gmail throttling, provider outage, token corruption, and forced ambiguous writes were not
induced against the connected account. Those destructive or non-deterministic cases were exercised
with controlled adapters instead. The real provider journey proves the integration boundary; the
fault harness proves fail-closed behavior, reconciliation, and replay safety without revoking the
pilot account or deliberately creating remote duplicates.

The Gmail transport now has explicit tests for:

- expired access (`401`) becoming a reauthorization requirement;
- rate limiting (`429`) becoming a safe provider-unavailable result;
- provider outage (`503`) becoming a safe provider-unavailable result;
- provider timeout and unknown outcomes remaining retry-safe or reconcilable.

## Performance boundary

The authenticated browser control surface does not expose the W3C `PerformanceObserver` API. The
recorded 375 ms value is therefore a bounded primary-content readiness measurement from warm reload
start until the main `Cases` heading was visible, not a field or lab LCP claim. Production Web Vitals
telemetry should collect exact LCP after promotion. The bounded pilot gate passed, and the browser
reported no runtime errors after reload.

## Operational controls

- Connected inbox, Gmail adapter, scheduled sync, push, draft write-back, and inbox-to-AI transfer
  are all default-off feature flags.
- Rollback disables draft write-back first, then scheduled sync, then the Gmail adapter.
- Imported evidence remains available after disconnect; credentials are removed and provider
  revocation is recorded separately.
- Replay keys and immutable approval snapshots prevent duplicate or changed draft delivery.
- Retention state is versioned and non-destructive; destructive retention execution remains outside
  the controlled-pilot boundary.
- Runbooks cover activation, rollback, incident recovery, backup/restore, credential rotation, and
  post-environment verification.

## Hosted limitations

The hosted application currently uses a Clerk development instance. Browser verification produced
only Clerk's development-key warning and no application runtime error. A production Clerk instance,
distributed rate limiting, centralized alerting, and a production restore drill remain promotion
requirements, not blockers for the controlled pilot or portfolio demonstration.

## Related evidence

- [Hosted connected draft acceptance](../../hosted-connected-draft-acceptance/2026-08-23/README.md)
- [Developer workflow benchmark](../../developer-workflow-benchmark/REPORT.md)
- [Connected Inbox and RAG V2 activation runbook](../../../runbooks/CONNECTED_INBOX_AND_RAG_V2_ACTIVATION.md)
- [Deployment and rollback runbook](../../../runbooks/DEPLOYMENT_AND_ROLLBACK.md)
- [Incident recovery runbook](../../../runbooks/INCIDENT_RECOVERY.md)
