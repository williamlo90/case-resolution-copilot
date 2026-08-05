# Signed Webhook Activation

Status: Implementation complete; live client endpoints and secrets are not yet activated

## Scope

The generic webhook pair keeps the product independent from a specific helpdesk, billing platform,
or account system:

- `POST /api/intake/cases` receives a complete support case snapshot.
- The controlled-action adapter sends `execute`, `reconcile`, and `health` operations to one
  configured HTTPS endpoint.

Both directions use an HMAC-SHA256 signature. Secrets remain in deployment settings and are never
stored in connection records, API responses, audit events, or Git.

This implementation is an integration boundary, not evidence that a client system is connected.
Do not describe the external-provider gate as complete until a sandbox endpoint has passed the
failure matrix below.

## Shared Signature Contract

Headers:

```text
X-Support-Copilot-Timestamp: <Unix timestamp in seconds>
X-Support-Copilot-Signature: v1=<lowercase HMAC-SHA256 hex>
```

Signed bytes:

```text
<timestamp>.<exact raw JSON request body>
```

The receiver must:

1. Reject missing or invalid signatures.
2. Reject timestamps outside the configured replay window.
3. Compare signatures in constant time.
4. Apply request-size limits before parsing.
5. Preserve idempotency for repeated event or action IDs.

## Case Intake Activation

Add these values to the backend deployment only:

```dotenv
SUPPORT_COPILOT_CASE_SOURCE_PROVIDER=signed_webhook
SUPPORT_COPILOT_INTEGRATION_ORGANIZATION_ID=ORG-0001
SUPPORT_COPILOT_CASE_WEBHOOK_SECRET=<at least 32 random characters>
SUPPORT_COPILOT_CASE_WEBHOOK_MAX_AGE_SECONDS=300
```

Redeploy the backend. Startup registers `Case intake webhook` for the configured organization.
The client case source then posts a signed payload to:

```text
https://<backend-host>/api/intake/cases
```

The payload contains:

- a stable `event_id`;
- case category, issue, urgency, risk, due time, and optional impact;
- the original customer request;
- a customer snapshot;
- one or more business-object snapshots.

The same signed `event_id` and payload returns the original case with `duplicate: true`. Reusing an
event ID with different case data returns `409 case_source_conflict`. Concurrent duplicate deliveries
are serialized in PostgreSQL, so they cannot create two cases.

## Controlled Action Activation

First deploy a client-owned sandbox endpoint that accepts signed JSON at one HTTPS URL. Then add:

```dotenv
SUPPORT_COPILOT_ACTION_TARGET_PROVIDER=signed_webhook
SUPPORT_COPILOT_INTEGRATION_ORGANIZATION_ID=ORG-0001
SUPPORT_COPILOT_ACTION_WEBHOOK_URL=https://<sandbox-host>/<action-path>
SUPPORT_COPILOT_ACTION_WEBHOOK_SECRET=<at least 32 random characters>
SUPPORT_COPILOT_ACTION_WEBHOOK_TIMEOUT_SECONDS=5
```

Redeploy the backend. In **Connections**, open **Controlled action webhook** and select
**Test connection**. The connection remains blocked until this check succeeds.

The endpoint receives three operation values:

### `health`

Response:

```json
{
  "status": "healthy",
  "detail": "Sandbox target is ready."
}
```

### `execute`

The request includes `provider_type` and an `action` object with:

- `action_id`
- `action_type`
- `target`
- string-valued `parameters`
- `idempotency_key`

The receiver must use `idempotency_key` as a durable unique key before changing external state.

Successful response:

```json
{
  "external_reference": "TARGET-1001",
  "idempotency_key": "<the exact request key>",
  "status": "completed",
  "data": {
    "result": "accepted"
  },
  "duplicate": false
}
```

### `reconcile`

This operation is read-only. It must never perform the action again.

Response when found:

```json
{
  "found": true,
  "receipt": {
    "external_reference": "TARGET-1001",
    "idempotency_key": "<the exact request key>",
    "status": "completed",
    "data": {},
    "duplicate": false
  },
  "detail": "The target confirmed the action."
}
```

Use `found: false` only when the target can prove no matching change exists. Use `found: null` when
the outcome cannot be established.

## Required Failure Matrix

Record one attributable result for each case:

| Scenario | Required product result |
| --- | --- |
| Invalid case signature | `401`; no case or audit payload created |
| Stale case timestamp | `401`; no case created |
| Duplicate case event | Same case; `duplicate: true` |
| Changed duplicate event | `409`; existing case unchanged |
| Oversized or invalid case body | `413` or `422`; no case created |
| Any non-success response after dispatch | Outcome unknown; reconcile before retry |
| Connection failure before send | Not attempted; safe retry may be offered |
| Timeout after dispatch | Outcome unknown; blind retry blocked |
| Oversized action response | Outcome unknown; reconciliation required |
| Invalid success receipt | Outcome unknown; reconciliation required |
| Duplicate action key | Same external receipt; no second change |
| Reconciliation target absent | Safe only after `found: false` |
| Reconciliation unavailable | Outcome remains unknown |
| Revoked or rotated secret | Connection check fails; action remains blocked |

## Rotation And Rollback

For rotation, update both ends during a controlled window, redeploy, and run **Test connection**
before executing a newly approved action.

For rollback:

```dotenv
SUPPORT_COPILOT_CASE_SOURCE_PROVIDER=disabled
SUPPORT_COPILOT_ACTION_TARGET_PROVIDER=deterministic
```

Keep `SUPPORT_COPILOT_INTEGRATION_ORGANIZATION_ID` during the rollback deployment. Startup marks the
previous runtime connections as setup-required without deleting cases, action attempts, receipts, or
audit history.

Existing actions remain bound to the connection selected when the review was approved. Validate the
new connection before creating the review used for sandbox acceptance.
