# Operational Controls

Status: Implemented and covered by deterministic, contract, and static verification.

## Scope

This milestone adds organization-owned governance around the case-resolution workflow:

- business quality reporting with attributable case evidence;
- exportable case audit history;
- in-app notifications and a durable, redacted delivery outbox;
- member role/status administration and invitation revocation;
- versioned general, approval, notification, security, and retention settings;
- non-destructive case retention/redaction state.

These controls remain inside the modular monolith and are tenant-scoped. They do not require an
identity vendor, email provider, model provider, browser, worker, or real credential.

## API

| Method | Route | Authority | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/quality` | Supervisor, administrator, auditor | Read business metrics and attributable evaluated-case evidence |
| `GET` | `/api/quality/cases/{case_id}` | Supervisor, administrator, auditor | Read quality evidence for one visible case |
| `POST` | `/api/cases/{case_id}/audit-export` | Administrator, auditor | Generate and audit a case-scoped JSON export |
| `GET` | `/api/notifications` | Active member | Read only the authenticated member's notifications |
| `POST` | `/api/notifications/{notification_id}/read` | Recipient | Mark one exact notification version read |
| `POST` | `/api/notifications/read-all` | Recipient | Mark the recipient's unread notifications read |
| `PATCH` | `/api/members/{member_id}` | Administrator | Change role or active/deactivated state |
| `POST` | `/api/invitations/{invitation_id}/revoke` | Administrator | Revoke one pending invitation version |
| `GET` | `/api/settings/{section}` | Administrator | Read typed organization settings or explicit defaults |
| `PUT` | `/api/settings/{section}` | Administrator | Save one exact settings version |

The supported settings sections are `general`, `approvals`, `notifications`, `security`, and
`retention`. Request bodies repeat the section as a discriminated type; a URL/body mismatch returns
`422`.

## Approval Rules

Financial administrator limits are organization-owned decimal values keyed by three-letter currency
code. A currency without a configured limit fails closed to administrator review. The settings
version is copied into every new review snapshot.

Changing approval settings does not rewrite historical authorization:

- an open review bound to the previous settings version becomes stale;
- reserve and decide commands recheck the settings row under lock;
- a new resolution review is required;
- a completed review keeps the exact historical rule snapshot that was authorized.

The requirement for a human decision reason cannot be disabled.

## Member Safety

Member changes use optimistic concurrency and append an organization audit event. The backend:

- derives administrator authority from the authenticated actor;
- prevents self-demotion and self-deactivation;
- prevents removal of the last active administrator;
- does not turn an existing membership back into an invitation;
- revokes only pending invitations;
- never accepts a client-supplied tenant or permission set.

## Notifications And Outbox

Notifications are recipient-scoped and use an idempotent organization/recipient/event key. The
outbox stores a destination fingerprint and stable resource identifiers, never a raw email address,
phone number, credential, or provider token.

`scripts/project_notifications.py` is an explicit, one-shot deterministic projector for:

- cases near or past their response limit;
- reviews waiting for an authorized decision;
- actions whose outcome must be checked.

There is no hidden scheduler or background process. In-app delivery is recorded immediately. Email
intent is created only when enabled and remains pending until a real provider is activated and
verified in the post-credential phase.

## Quality Semantics

`/api/quality` reports business evidence rather than model-call or token counts. It returns:

- expected-decision match rate;
- unsafe-action blocking evidence;
- policy-evidence coverage;
- actions waiting for an outcome check;
- open cases, waiting reviews, and action outcome counts;
- the evaluator, evaluation source, case, expected result, observed result, policy support, and
  impact for every returned projection.

`scripts/seed_quality.py` adds three labelled deterministic demo projections covering decision
quality, safety, and reliability. These rows demonstrate the contract; they are not a production
quality benchmark or a claim about a real model.

## Audit Export

Audit export includes the organization and generic case identifiers, external/source references,
the optional legacy task identifier, governance state, actor attribution, correlation IDs, and
events related to the case, its reviews, and its actions. Unknown historical actors remain
`unavailable`; the exporter does not invent a person or role.

The export itself appends `case.audit_exported`. Stored event details pass through recursive
redaction before leaving the API.

## Retention State

`case_data_governance` records policy version, conversation and audit retention dates, legal-hold
state, redaction state, and a source fingerprint. Audit retention cannot end before conversation
retention.

`scripts/backfill_data_governance.py` is dry-run by default and writes only with `--apply`. The
backfill records state; it does not delete, purge, anonymize, or rewrite customer data. Actual
retention execution remains blocked until a disposable PostgreSQL environment, backup/restore
procedure, legal requirements, and post-credential security checks are supplied.

Existing governance rows remain bound to the policy version recorded when they were created.
Running the backfill again only fills missing rows; it does not silently recalculate prior
retention dates after a settings change.

## Activation

After migration and deterministic identity/case seeds:

```powershell
python scripts/seed_operational_settings.py
python scripts/seed_quality.py
python scripts/project_notifications.py
python scripts/backfill_data_governance.py
python scripts/backfill_data_governance.py --apply
```

Review dry-run output before `--apply`. None of these commands should be pointed at production data
during the current portfolio/demo phase.
