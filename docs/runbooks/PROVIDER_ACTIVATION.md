# External Provider Activation

Status: Core database, Clerk, and OpenAI are active; signed case/action adapters are implemented but
not yet connected to client-owned endpoints

## Rule

Activate one provider in one sandbox or test account at a time. A successful happy path is not
sufficient evidence. No provider may weaken tenant scope, approval authority, idempotency, redaction,
or outcome-unknown handling.

## Preconditions

- Document provider owner, purpose, data sent, data retained, limits, cost, timeout, retry semantics,
  credential rotation, revocation, and rollback.
- Use least-privilege credentials separated by environment.
- Confirm provider terms and data handling for customer and business data.
- Keep secret values outside Git, logs, fixtures, screenshots, and captured evidence.
- Define a deterministic fallback only for non-consequential demo behavior.

## Activation Order

1. Read-only case or context source.
2. Model and optional embedding provider.
3. One controlled action target with a sandbox and receipt lookup.
4. Notification provider.
5. Telemetry provider.

For each provider, verify authentication failure, timeout, invalid response, rate limit, revocation,
and recovery before moving to the next.

The provider-neutral case and action contract is documented in
`docs/runbooks/SIGNED_WEBHOOK_ACTIVATION.md`.

## Side-Effect Provider Gate

- Bind every write to an approved action and stable idempotency key.
- Record attempt identity before the provider call.
- Redact request and response evidence.
- Treat timeout after dispatch as outcome unknown.
- Reconcile by external reference before permitting another write.
- Never retry an unknown outcome blindly.

## Rollback

Disable the affected connection, block commands that require it, preserve attempts and receipts, and
reconcile any uncertain outcomes. Provider removal must not delete audit lineage or silently mark an
unknown action as failed.

## Not Yet Proven

The signed webhook contracts and deterministic failure tests exist, but no client-owned case source
or controlled-action endpoint has produced live sandbox evidence. Notification and telemetry
providers also remain deferred.
