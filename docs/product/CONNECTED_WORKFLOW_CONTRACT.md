# Connected Decision Workflow - Product And UX Contract

Status: Approved for implementation planning

Decision date: 2026-08-12

Owner: Product and engineering

Depends on:

- `docs/product/PRODUCT_CONTRACT.md`
- `docs/product/UX_ARCHITECTURE.md`

## 1. Decision

The next product increment connects Case Resolution Copilot to a real test inbox. Gmail is the first
adapter, while the product domain remains provider-neutral.

The approved workflow is:

`Email thread -> Case evidence -> Policy-backed Decision Brief -> Human decision -> Approved email draft -> Audit`

The connection makes the existing decision workflow usable from a real work source. It does not turn
the product into a general email client, helpdesk replacement, or autonomous support agent.

## 2. Product Outcome

A support team must be able to move one customer conversation from an inbox into a governed decision
without manually copying the thread between tools. The product should reduce the effort needed to:

1. understand the customer request;
2. identify facts and missing information;
3. find the policy version that applied at the relevant time;
4. prepare an authorized resolution;
5. create a reviewable response draft; and
6. reconstruct every material step later.

The product succeeds only when the connected workflow remains understandable and safe when data is
late, incomplete, duplicated, stale, or temporarily unavailable.

## 3. Implementation Boundary

### Provider-neutral product concepts

- **Inbox connection:** an authorized source of customer conversations.
- **External conversation:** a provider thread linked to one workspace and case.
- **External message:** an immutable message observation with source and received time.
- **Sync status:** the known freshness and health of an inbox connection.
- **Response draft:** editable customer-facing text that may be written back to the source.
- **Draft delivery:** the recorded attempt and result of creating a provider-side draft.

Provider names, OAuth scopes, cursor formats, and message identifiers stay inside adapters and
administrator diagnostics. Case, conversation, evidence, review, and action contracts must not gain
Gmail-specific required fields.

### First adapter

Gmail is selected for the controlled implementation because it supports a realistic email workflow
with one test account and lower setup cost than a full helpdesk integration. The architecture must
allow a later Outlook or helpdesk adapter without changing the shared case lifecycle.

### Authority boundary

- The inbox remains authoritative for email messages and provider-side drafts.
- Case Resolution Copilot remains authoritative for case state, decision evidence, review, and audit.
- Published policy versions remain the only policy corpus used to ground a recommendation.
- Application code, not the model, decides permissions, review requirements, and whether draft
  creation is currently allowed.

## 4. Roles And Responsibilities

### Operations Administrator

- Connects, tests, reauthorizes, disables, or removes an inbox connection.
- Sees the requested read and write capabilities before authorization.
- Chooses whether import is active after a successful connection test.
- Can inspect connection health without seeing secret values.

### Support Specialist

- Opens imported cases and reads the synchronized conversation.
- Reviews the source and freshness of imported information.
- Corrects the case summary and response draft.
- Requests information or submits the proposed resolution for review.
- Creates a provider draft only when the backend confirms that required review is complete.

### Supervisor

- Reviews the exact case, evidence, policy, proposal, and response snapshot.
- Approves, requests changes, rejects, or escalates the proposed resolution.
- Does not approve a newer email or changed proposal through an older review snapshot.

### QA Or Auditor

- Reads message-import, decision, approval, and draft-delivery history.
- Can trace a draft to the proposal and evidence snapshot that authorized it.
- Cannot connect an inbox, edit a decision, create a draft, or send an email.

## 5. Core User Journeys

### Journey A: Connect a test inbox

1. An administrator opens **Connections** and chooses **Connect inbox**.
2. The product explains that it will read conversations and create drafts but will not send email.
   It also states that Google's draft-management consent technically permits sending even though
   this product exposes no send command.
3. The administrator continues to Google and authorizes the requested access.
4. The product verifies the account, displays the connected address, and runs a connection test.
5. The administrator activates import.
6. The connection shows its health, last successful sync, and available recovery command.

The connection is not marked active merely because an OAuth callback returned. Account identity,
required capability, tenant ownership, and a provider request must all be verified.

### Journey B: Import an email as a case

1. The connector observes a previously unseen email thread.
2. The system checks the provider thread mapping and import identity.
3. A new thread creates one case; a known thread adds only unseen messages to its existing case.
4. The case records the source address, provider, external reference, and sync freshness.
5. The specialist sees **New email** or **New reply**, not an implementation event name.
6. Duplicate delivery or replay does not create a duplicate case or message.

For a new reply on a completed case, the product preserves the completed decision and asks an
authorized user to choose **Reopen case** or **Create follow-up case**. It does not silently alter a
historical resolution.

### Journey C: Prepare a policy-backed decision

1. The specialist reads the conversation and connected business evidence.
2. The workspace separates verified facts, information needed, relevant policy, inference, and
   uncertainty.
3. Policy retrieval considers tenant, category, applicability, effective date, and publication
   status.
4. The suggested resolution cites the exact policy version and source clauses it used.
5. If evidence is insufficient or policies conflict, the interface asks for information or review
   instead of presenting a confident answer.
6. The specialist revises the resolution and response draft before submitting it.

Email content is case evidence. It must not be mixed into the governed policy corpus or treated as a
business rule merely because a sender states one.

### Journey D: Review a consequential resolution

1. The supervisor opens the review from **Reviews** or the case activity.
2. The interface highlights impact, uncertainty, missing information, policy version, and proposed
   actions.
3. The supervisor approves, requests changes, rejects, or escalates with an attributable reason.
4. A changed conversation, policy, proposal, authority rule, or material business snapshot makes the
   submitted review stale.
5. A stale review cannot authorize a draft or external action until resubmitted.

### Journey E: Create an approved email draft

1. The case shows **Create email draft** only when the current user and current snapshot are eligible.
2. Confirmation names the recipient, subject, source inbox, and that no email will be sent.
3. The backend binds the request to the approved proposal and evidence fingerprint.
4. Gmail creates or returns one draft in the original thread.
5. The product stores the provider draft reference and shows **Draft ready in Gmail**.
6. The user opens Gmail to inspect and send it manually.

Retries must not create multiple drafts for the same authorized snapshot. An uncertain provider
result becomes **Check draft status**, not **Try again**.

## 6. Information Architecture Changes

### Connections

The existing `/connections` page gains:

- **Connect inbox** as the primary command for administrators;
- provider, connected account, permitted capabilities, and connection owner;
- health, last successful sync, and age of the last known data;
- **Test connection**, **Reauthorize**, **Pause import**, and **Remove** commands;
- plain-language setup and recovery guidance.

A connection detail may use `/connections/:connectionId`. Provider callbacks are implementation
routes and must not become navigation destinations.

### Cases queue

Imported cases add scannable source information without increasing default table density
unnecessarily:

- an inbox source icon and accessible label;
- **New reply** when an unread synchronized message needs attention;
- sync warnings only on affected cases;
- filters for `Inbox source` and `Needs sync attention`.

### Case workspace

The existing **Conversation** section gains:

- sender, recipients, received time, and message direction;
- source link when permitted;
- last synchronized time;
- a visible marker for omitted, unsupported, or unavailable attachments;
- preservation of the response draft when a sync or generation request fails.

The primary decision sections remain **Case summary**, **Verified facts**, **Information needed**,
**Relevant policy**, **Suggested resolution**, **Risk checks**, and **Response draft**.

### Reviews and activity

Review snapshots show the last included message and conversation fingerprint. Activity records:

- inbox connected, reauthorized, paused, disconnected, or removed;
- case imported and message synchronized;
- sync failed and recovered;
- review submitted and decided;
- response draft created, found after reconciliation, or failed safely.

Raw OAuth tokens, full provider payloads, and model prompts never appear in business activity.

## 7. User-Facing State Contract

### Connection states

| State | UI label | Primary guidance |
| --- | --- | --- |
| Not configured | Not connected | Connect inbox |
| Authorization in progress | Connecting | Finish sign-in |
| Verified and importing | Connected | View sync status |
| Temporarily unavailable | Needs attention | Test connection |
| Authorization expired | Sign in again | Reauthorize |
| Import paused | Import paused | Resume import |
| Deliberately removed | Disconnected | Connect inbox |

### Conversation freshness

| Condition | UI behavior |
| --- | --- |
| Current | Show exact last-sync time as secondary information |
| Sync in progress | Preserve the existing conversation and show quiet progress |
| Delayed | Show the age of the last known snapshot |
| Failed | Preserve existing data and explain which source is affected |
| Material update after review | Block the old review and identify what changed |

### Draft delivery states

| State | UI label | Permitted next step |
| --- | --- | --- |
| Not eligible | Complete required review | Open review requirements |
| Ready | Ready to create draft | Create email draft |
| In progress | Creating draft | Wait; no duplicate command |
| Completed | Draft ready in Gmail | Open draft |
| Safe failure | Draft was not created | Retry when permitted |
| Outcome unknown | Check draft status | Reconcile before retry |

## 8. Plain-Language Contract

Use these terms in normal operations:

| Use | Avoid |
| --- | --- |
| Connect inbox | Configure source adapter |
| New email / New reply | Provider event received |
| Last updated | Sync cursor timestamp |
| Relevant policy | RAG result |
| Suggested resolution | Model generation |
| Needs review | Approval gate |
| Draft ready in Gmail | Write-back succeeded |
| Check draft status | Reconcile unknown side effect |
| Sign in again | Refresh token invalid |

Every disabled command explains what must happen next. A confidence value never appears without its
supporting evidence, uncertainty, and information gaps.

## 9. Evidence And Attachment Contract

- Message headers and bodies are evidence with provider identity and observed time.
- Provider timestamps and application observation timestamps are stored separately.
- Attachment name, type, size, source message, and availability are always represented when known.
- Attachment content is processed only for explicitly supported types and configured size limits.
- Unsupported or unavailable content remains visible as an evidence gap; it is not silently ignored.
- Quoted text and signatures may be collapsed for reading but the preserved source remains traceable.
- A customer statement may support what the customer claimed, not that the claim is independently
  verified.

Exact file allowlists, size limits, retention, and redaction behavior are Phase 2 security and data
design decisions.

## 10. Functional Requirements

- **CW-001:** An administrator can connect one Gmail test inbox to one workspace.
- **CW-002:** The product displays both its read/draft behavior and the broader technical wording of
  the Gmail consent before authorization.
- **CW-003:** A provider thread maps to at most one active case per workspace unless a user explicitly
  creates a follow-up case.
- **CW-004:** Replayed imports do not duplicate cases or messages.
- **CW-005:** New messages update the conversation without replacing prior evidence.
- **CW-006:** Imported content records source, observed time, and freshness.
- **CW-007:** A material message change invalidates an older review snapshot.
- **CW-008:** Policy retrieval is tenant-, version-, publication-, and effective-date aware.
- **CW-009:** A recommendation distinguishes facts, policy, inference, uncertainty, and missing data.
- **CW-010:** Draft creation requires current backend authorization and a current decision snapshot.
- **CW-011:** The connector can create a Gmail draft but cannot send an email.
- **CW-012:** Draft creation is idempotent or reconciled before retry.
- **CW-013:** Disconnecting an inbox stops future imports without deleting historical case evidence.
- **CW-014:** Every material connection, import, review, and draft event is attributable and auditable.
- **CW-015:** Auditor access remains read-only across the connected workflow.

## 11. Non-Functional Requirements

- Tenant identity is enforced server-side for every connection and external reference.
- Credentials and refresh tokens are server-only, encrypted at rest, redacted from logs, and never
  returned after creation.
- Imports and draft commands tolerate retries, duplicate delivery, process restarts, and rate limits.
- Provider outages do not erase the last known conversation or user-authored response draft.
- Sync work is bounded and resumable; opening a page does not start an unbounded mailbox scan.
- UI loading states preserve stable layout and do not repeatedly redirect through authentication.
- Accessibility, keyboard operation, mobile priority, and WCAG AA requirements from the UX
  architecture remain binding.
- User-facing operations use business language; provider diagnostics are restricted to authorized
  administrators.

## 12. Success Measures

The increment instruments, but does not pre-claim:

- time from an eligible email becoming available to a case becoming visible;
- duplicate case and duplicate message rate;
- time from case open to correct disposition;
- time from decision approval to response draft ready;
- manual inputs needed to reach the correct disposition;
- policy, version, and approval correctness;
- unsupported fact and unsupported citation count;
- draft creation safe-failure and outcome-unknown rate;
- duplicate draft count after replay or retry;
- connection failure and recovery time;
- OpenAI calls, latency, tokens, and cost per evaluated case.

The existing six-case developer benchmark remains a calibration set. It cannot support a broad
production-effectiveness claim by itself.

## 13. Acceptance Criteria

Phase 1 is complete when this contract establishes that:

- Gmail is the first adapter while the domain remains provider-neutral;
- users can explain what the product reads and what it can write;
- no product path sends customer email automatically;
- every role has explicit authority in the connected workflow;
- import, update, stale-review, approval, and draft journeys have defined behavior;
- duplicate and outcome-unknown scenarios do not encourage blind retries;
- case evidence and governed policy evidence remain separate;
- connection, conversation, and draft states use plain language;
- the exact implementation requirements are traceable through `CW-001` to `CW-015`;
- Phase 2 can design interfaces, schema, OAuth, security, and failure semantics without inventing new
  product behavior.

## 14. Explicit Non-Goals

This increment does not include:

- a full inbox user interface;
- multiple inboxes per workspace;
- bulk historical mailbox import;
- outbound email sending;
- autonomous replies or autonomous case closure;
- Gmail labels, filters, calendar, contacts, or general account access;
- a production helpdesk migration;
- customer-data model training;
- policy retrieval from ungoverned email content;
- arbitrary model-generated provider calls;
- a claim that the workflow saves time before the benchmark is executed.

## 15. Phase 2 Handoff

Phase 2 must produce:

1. connector ports and Gmail adapter boundaries;
2. OAuth capability and threat model;
3. connection, external-thread, message, checkpoint, and draft-delivery schemas;
4. idempotency and reconciliation semantics;
5. message and attachment retention and redaction decisions;
6. RAG versioning and retrieval design;
7. sequence diagrams for import, stale review, and draft delivery;
8. migration, feature-flag, observability, and rollback design.

Implementation must not begin by placing Gmail logic directly inside case, review, or frontend route
modules. The architecture phase owns the adapter boundary first.

Phase 2 design is recorded in:

- `docs/adr/ADR-007-provider-neutral-connected-inbox.md`;
- `docs/backend/CONNECTED_INBOX_ARCHITECTURE.md`; and
- `docs/backend/GOVERNED_RAG_V2.md`.
