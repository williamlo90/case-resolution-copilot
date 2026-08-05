# Case Resolution Copilot - Product Contract

Status: Approved product contract

Original decision: 2026-07-21

Reconstruction review: 2026-08-05

Owner: Product and engineering

Decision type: Product scope and delivery contract

This document is the source of truth for product scope, authority, and acceptance. Historical
pre-pivot plans remain available in the archived repository, but they are not active requirements.

## 1. Product Decision

Build a business-to-business SaaS application that helps support teams make, approve, execute, and
audit high-impact customer resolution decisions.

Product name:

> Case Resolution Copilot

Product category:

> Support Decision and Resolution Platform

Positioning:

> A policy-governed decision workspace for complex support cases. It works above an existing
> helpdesk and business systems; it does not replace them.

The initial product is generic at its core. Travel refund is retained only as one optional scenario
template and must not define the default schema, navigation, copy, or product claim.

## 2. Problem

Support teams handle cases where a normal reply or FAQ is insufficient. Examples include billing
disputes, refunds, account recovery, policy exceptions, replacements, and high-value compensation.

These cases commonly fail because:

- relevant customer, account, and policy evidence is spread across systems;
- agents interpret policies inconsistently;
- approval requirements are unclear or handled outside the case record;
- consequential actions are retried without reliable side-effect knowledge;
- managers cannot reconstruct why a decision was made;
- generic AI assistants generate text but do not enforce business authority.

## 3. Target Customer

### Initial customer profile

- Digital businesses with an established customer support team.
- Approximately 20 to 500 support agents.
- An existing helpdesk, CRM, billing platform, order system, or internal support API.
- Written policies or SOPs that govern customer remedies.
- Supervisor approval for financial, account, compliance, or exception decisions.
- A need for faster resolution without losing control or auditability.

### Economic buyer

- Head of Customer Support.
- Customer Support Operations Manager.
- Customer Experience Operations Lead.
- Risk or Trust Operations Manager where support decisions have material impact.

### Primary users

- **Support Specialist:** investigates a case and prepares a resolution.
- **Supervisor:** reviews high-impact or exceptional resolutions.
- **Operations Administrator:** configures policies, rules, users, and integrations.
- **QA or Auditor:** reviews decision quality, compliance, and operational evidence.

An end customer is affected by decisions but is not a direct user of this SaaS workspace in the MVP.

## 4. Core Job To Be Done

When a customer case requires judgment or a consequential action, a support team needs to assemble
the facts, apply the correct policy, choose an authorized resolution, and prove what happened without
moving the decision across disconnected tools.

The product must help the team answer five questions:

1. What happened?
2. What evidence and policy apply?
3. What resolution is recommended, and what remains uncertain?
4. Who is authorized to approve and execute it?
5. Did the action complete, fail safely, or produce an uncertain side effect?

## 5. Product Promise

The application provides one governed workflow from complex support case to verified outcome:

`Case intake -> Evidence review -> Resolution proposal -> Human decision -> Controlled action -> Verified outcome -> Audit`

The product must reduce decision friction while preserving human authority. It must not claim that AI
can autonomously resolve every case.

## 6. Product Principles

1. **Decision support before automation.** The system first improves the quality and consistency of
   decisions; automation is allowed only through explicit controls.
2. **Policy evidence before confidence.** A confident recommendation without applicable evidence is
   not considered ready.
3. **Human authority is explicit.** Approval comes from role and business rules, never from the model.
4. **Actions have known outcomes.** Success, safe failure, and uncertain side effects are separate
   states with different recovery paths.
5. **Generic core, concrete templates.** Shared concepts remain domain-neutral while scenario
   templates provide realistic fields, policies, and actions.
6. **Plain language in the product.** Users see business terms, not orchestration, retrieval, model,
   schema, or provider jargon unless they are in an administrator diagnostic view.
7. **Existing systems remain authoritative.** The application coordinates decisions; it does not
   silently become the system of record for customers, orders, subscriptions, or payments.

## 7. MVP Scope

### Organization and access

- One tenant-isolated organization workspace.
- User invitation and membership.
- Roles for specialist, supervisor, administrator, and auditor.
- Configurable approval thresholds and action permissions.
- Workspace-level audit events for administrative changes.

### Onboarding and configuration

- A setup checklist that can be resumed.
- Organization profile and default locale/time zone.
- Policy upload and publication workflow.
- At least one case-source connection or a clearly labeled demo source.
- At least one action connection or the controlled action simulator.
- A test case that validates configuration before activation.

### Case operations

- Case Queue with ownership, status, urgency, risk, SLA, and filtering.
- Case Workspace with conversation, customer context, business context, evidence, policy, and history.
- AI-assisted summary, classification, missing-information detection, and resolution proposal.
- A visible separation between facts, policy evidence, inference, and uncertainty.
- Specialist actions to revise, request information, submit for review, or escalate.

### Review and approval

- Review Queue for cases requiring a human decision.
- Full review snapshot bound to the case, proposal, evidence, policy, and rule versions.
- Approve, request changes, reject, or escalate decisions with attributable reasons.
- Backend authority remains the final source of truth for any decision.

### Controlled actions

- Registered action types with typed parameters and expected outcomes.
- Idempotency and duplicate-delivery protection.
- Action status for pending, completed, failed safely, outcome unknown, and recovery required.
- Manual reconciliation path after an uncertain side effect.

### Governance and reporting

- Append-only case decision and action timeline.
- Operational dashboard for queue health, resolution time, review rate, and action outcomes.
- Quality view for recommendation acceptance, policy coverage, and reopened cases.
- Exportable audit record for a single case.

### Initial scenario templates

The MVP demonstrates that the core is not travel-specific through three templates:

1. **Billing dispute:** verify charges and propose reversal, credit, or explanation.
2. **Refund request:** assess eligibility and propose refund, partial refund, credit, or rejection.
3. **Account access recovery:** verify evidence and propose a controlled recovery action or specialist
   escalation.

Travel refund may be included as sample data inside the refund template, but it is not the default
tenant identity.

## 8. Explicit Non-Goals

The MVP will not:

- replace Zendesk, Intercom, Salesforce, or another complete helpdesk;
- provide a full omnichannel messaging inbox;
- host a customer-facing chatbot;
- allow arbitrary actions generated by a model;
- support a no-code workflow builder for every possible business process;
- provide marketplace billing, metered pricing, or self-service subscription management;
- claim compliance certification, production SLOs, or enterprise security without evidence;
- train models on client data by default;
- expose chain-of-thought, secrets, or raw provider payloads;
- make cross-tenant data visible through search, analytics, logs, or administration.

## 9. Generic Domain Contract

The shared product model uses these concepts:

- **Organization:** tenant boundary for people, configuration, data, and integrations.
- **WorkspaceMember:** user membership, role, status, and authority.
- **Connection:** configured external system and its permitted capabilities.
- **Case:** support work item requiring investigation or resolution.
- **Conversation:** customer messages and internal communication relevant to the case.
- **CustomerSnapshot:** versioned customer context received from an authoritative system.
- **BusinessObjectSnapshot:** versioned order, subscription, invoice, account, delivery, or other
  scenario-specific context.
- **PolicyVersion:** published business policy or SOP with applicability metadata.
- **Evidence:** a cited case fact or policy clause with source and freshness.
- **ResolutionProposal:** versioned recommended outcome, rationale, uncertainty, and proposed actions.
- **RiskAssessment:** deterministic triggers that control review and execution.
- **ReviewDecision:** attributable human decision bound to the reviewed snapshot.
- **ActionDefinition:** configured action type, parameter schema, permissions, and expected outcome.
- **ActionAttempt:** one idempotent attempt and its side-effect knowledge.
- **AuditEvent:** append-only record of a material user or system event.

Scenario-specific details belong in typed context and action adapters. They must not add booking,
passenger, itinerary, or airline fields to every case.

## 10. AI And Authority Contract

AI may:

- summarize conversations and structured context;
- classify case category, urgency, and missing information;
- retrieve and rank applicable policy evidence;
- propose a structured resolution and draft communication;
- state uncertainty and conflicts;
- support offline evaluation.

AI may not:

- create its own permissions or approval authority;
- approve its own proposal;
- execute unregistered or unapproved actions;
- invent customer facts or policy citations;
- hide conflicting evidence;
- perform arbitrary network calls;
- decide that an uncertain external side effect is safe to retry.

Deterministic application code controls tenant isolation, authorization, policy publication, approval
rules, action registration, idempotency, redaction, audit, and recovery requirements.

## 11. Integration Contract

The SaaS is an overlay, not the master database for the client's business objects.

- Case sources may include helpdesk APIs, email ingestion adapters, webhooks, or a demo source.
- Context sources may include CRM, billing, subscription, order, or account systems.
- Action targets may include payment, credit, order, account, messaging, or internal APIs.
- Every connection declares read and write capabilities separately.
- Credentials are tenant-scoped, encrypted, redacted, and never displayed after creation.
- The product records snapshots and receipts required to explain a decision without claiming to own
  the external record.
- Provider-specific errors are mapped to stable product states and plain-language recovery guidance.

## 12. Success Measures

The MVP must instrument, but must not pre-claim, these measures:

- Median time from case assignment to resolution decision.
- Percentage of proposals accepted without revision.
- Percentage of cases with applicable cited policy evidence.
- Percentage of high-impact actions executed with required approval.
- Reopened case rate after a completed resolution.
- Rate of safe failures and outcome-unknown actions.
- Time to reconcile outcome-unknown actions.
- Number of cross-tenant access violations, with a required target of zero.

Vanity metrics such as generated summaries, model calls, or token volume are not primary product
success measures.

## 13. Product Language Contract

Default user-facing terms:

| Use | Avoid in normal UI |
| --- | --- |
| Case | Task payload |
| Suggested resolution | Model output |
| Relevant policy | Retrieval result or RAG context |
| Needs review | Approval node |
| Action | Tool call |
| Activity history | Trace or span |
| Information needed | Missing context exception |
| Outcome unknown | Provider timeout after side effect |
| Try recovery steps | Compensation workflow |

Technical language is permitted only in administrator diagnostics and engineering evidence views.

## 14. Delivery Gates

The redesign is acceptable only when:

- default fixtures cover at least billing, refund, and account-access scenarios;
- no travel-only field is required by the generic case contract;
- tenant identity is visible and enforced on every protected resource;
- each role has a clear home view and cannot perform unauthorized actions;
- every recommendation separates facts, policy support, inference, and uncertainty;
- approval reviews display the exact snapshot being authorized;
- outcome-unknown actions cannot be retried blindly;
- onboarding can reach a useful demo state without external credentials;
- the product does not claim production readiness without database, security, integration, and
  operational evidence.

## 15. Open Decisions

These decisions are deliberately deferred until implementation planning:

- the first real helpdesk integration;
- the first real action provider;
- authentication vendor and organization provisioning method;
- commercial packaging and pricing;
- data residency and regulated-industry commitments;
- whether policy authoring remains upload-first or later gains structured rule editing.

Deferring these choices does not permit hard-coding a vendor into the generic domain model.
