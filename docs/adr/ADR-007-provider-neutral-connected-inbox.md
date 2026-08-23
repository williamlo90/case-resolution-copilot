# ADR-007: Keep the connected inbox behind provider-neutral ports

Status: Accepted for Connected Workflow Phase 2

Date: 2026-08-12

## Context

Case Resolution Copilot needs one real work-source integration. The first controlled workflow uses a
Gmail test inbox, but the product contract remains an overlay above existing inbox and helpdesk
systems. Gmail concepts must not become required case, conversation, review, or action concepts.

The existing backend is a modular monolith. PostgreSQL owns durable workflow truth, connection
records expose secret-free capabilities, and external action calls already use explicit gateways,
idempotency, and outcome-aware recovery. Inbox integration should extend those boundaries rather
than introduce provider calls inside routes or case repositories.

Gmail also presents two material constraints:

- draft creation requires `gmail.compose` or `gmail.modify`, and those scopes also permit sending;
- reliable push requires Cloud Pub/Sub, watch renewal, and polling fallback because notifications
  can be delayed or dropped.

## Decision

Introduce provider-neutral application ports for inbox authorization, message retrieval, sync, and
draft creation. Gmail is one adapter selected at runtime by a registered adapter key.

The shared write port contains `create_reply_draft`; it does not contain `send`, `send_draft`, or an
arbitrary provider-request escape hatch. The Gmail adapter may call `users.drafts.create` only. A
build-time source check and contract tests reject Gmail send endpoints.

Use PostgreSQL-backed sync jobs and leases as durable coordination. A manual command, scheduler, or
authenticated push notification may request the same bounded sync operation. The initial controlled
pilot uses explicit and scheduled incremental sync; Pub/Sub push is an optional later trigger, not a
dependency for the first implementation.

Store tenant OAuth refresh tokens only through a `CredentialVault` port. The first implementation
may use an encrypted PostgreSQL envelope with a server-held master key. Normal connection queries
must never load ciphertext or secret material.

Keep Gmail-derived case evidence separate from the governed policy corpus. OpenAI is never called
automatically during inbox import. Any later model call uses a minimized, consented, user-facing
request and remains subject to the AI data-governance gate.

## Rationale

- A narrow port prevents Gmail from leaking into the domain model.
- PostgreSQL jobs preserve idempotency and restart safety without adding Redis to the pilot.
- Pull-based incremental sync is enough for one controlled inbox and is simpler to operate than
  mandatory Pub/Sub.
- Separating credentials from connection metadata reduces accidental secret exposure.
- Omitting send from the port makes the product boundary testable even though the OAuth scope is
  technically broader than the product capability.
- Explicit AI activation avoids sending imported customer content to a model merely because an
  inbox was connected.

## Consequences

- Gmail remains suitable for a controlled test, but it is not the strongest production provider for
  cryptographic least privilege because the draft scope also permits sending.
- A stolen Gmail refresh token could exceed the product's intended capability. Encryption, strict
  adapter egress, token revocation, audit, and production verification are mandatory compensating
  controls; they do not erase that residual risk.
- Public production use may require Google restricted-scope verification and a security assessment.
- The encrypted PostgreSQL vault is a controlled-pilot implementation. Public production activation
  requires a managed key service or separately accepted evidence that the deployment key management
  meets Google's restricted-scope requirements.
- Testing-mode OAuth refresh tokens may expire after seven days, so `Sign in again` is a normal
  controlled-pilot state.
- Full mailbox import is not supported. Initial sync is bounded by label, age, and item limits.
- Pub/Sub can be added later through the same sync-request port without changing case logic.
- Outlook or a helpdesk adapter can replace Gmail without changing the shared workflow.

## Alternatives Rejected

- **Put Gmail calls in case services:** couples provider failures and OAuth details to core business
  logic and makes another provider expensive to add.
- **Use `gmail.modify`:** grants more mailbox mutation capability than the feature needs.
- **Claim OAuth-level draft-only access:** Gmail currently exposes no such scope for this web-server
  workflow.
- **Require Pub/Sub in the first pilot:** adds setup and failure modes while polling fallback is still
  required.
- **Poll the full inbox on page load:** creates unbounded latency, duplicate work, and a poor serverless
  failure boundary.
- **Store tokens on `connections`:** makes ordinary connection reads a secret-handling path.
- **Send messages automatically:** contradicts the product contract and removes the final human
  inspection boundary.
- **Use email as the policy corpus:** treats customer claims and ungoverned correspondence as business
  authority.

## References

- [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail synchronization](https://developers.google.com/workspace/gmail/api/guides/sync)
- [Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push)
- [Create a Gmail draft](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create)
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Google Workspace API user data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
