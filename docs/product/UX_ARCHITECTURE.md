# Case Resolution Copilot - UX Architecture

Status: Approved direction for UI/UX redesign  
Date: 2026-07-21  
Depends on: `docs/product/PRODUCT_CONTRACT.md`

Connected workflow amendment: `docs/product/CONNECTED_WORKFLOW_CONTRACT.md`

This document defines the user roles, information architecture, page responsibilities, core
journeys, interaction states, and usability rules for the SaaS client application. It is a UX
contract, not a visual mockup or implementation plan.

## 1. UX Objective

The application must make complex support decisions easier to understand and safer to complete.
Every primary screen should help a user answer one immediate question:

- **Queue:** What needs my attention now?
- **Case:** What happened, and what should I do next?
- **Review:** What exactly am I authorizing?
- **Action:** Did the approved change happen?
- **Policy:** Which rule is active and where does it apply?
- **Dashboard:** Where is the operation slowing down or becoming risky?
- **Setup:** What must be configured before the workspace can be used?

The interface must not require users to understand AI orchestration, retrieval systems, tool calls,
or internal state machines.

## 2. Roles And Home Views

### Support Specialist

Primary goal: resolve assigned cases correctly and on time.

Default home: **My Cases**.

Can:

- inspect cases and evidence;
- edit the suggested resolution and response draft;
- request missing information;
- submit a case for review;
- execute an action only when role and policy permit it.

Cannot approve a decision that requires a supervisor or change workspace policy.

### Supervisor

Primary goal: review consequential decisions and unblock the team.

Default home: **Reviews**.

Can:

- inspect the complete review snapshot;
- approve, request changes, reject, or escalate;
- assign or reassign cases;
- review failed and outcome-unknown actions;
- inspect team-level operational metrics.

Cannot alter the historical snapshot attached to a submitted review.

### Operations Administrator

Primary goal: configure a usable and governed workspace.

Default home: **Setup** until activation, then **Settings**.

Can:

- manage members and roles;
- configure connections and action permissions;
- upload, review, publish, and retire policies;
- configure approval rules and workspace defaults;
- run a configuration test case.

Cannot silently edit or delete historical business decisions.

### QA Or Auditor

Primary goal: determine whether decisions were consistent, supported, and correctly executed.

Default home: **Quality**.

Can:

- search completed cases and audit history;
- inspect policy and proposal versions;
- review decision and action outcomes;
- export a case audit record.

Read-only by default.

## 3. Global Information Architecture

Primary navigation:

1. **Cases**
2. **Reviews**
3. **Actions**
4. **Policies**
5. **Quality**

Administrative navigation:

6. **Connections**
7. **Team**
8. **Settings**

Global utilities:

- Organization switcher.
- Search.
- Notifications.
- Help and product status.
- User menu.

Navigation is permission-aware. Hidden modules must not remain reachable through a direct URL without
authorization. A disabled navigation item is shown only when it communicates a temporary setup
requirement and includes a clear path to resolve it.

## 4. Route Model

Recommended route structure:

```text
/onboarding
/cases
/cases/:caseId
/reviews
/reviews/:reviewId
/actions
/actions/:actionId
/policies
/policies/:policyId
/quality
/quality/cases/:caseId
/connections
/connections/:connectionId
/team
/settings/general
/settings/approval-rules
/settings/security
```

The organization context should be derived from the authenticated session or an explicit workspace
slug. It must never be inferred from untrusted client state alone.

## 5. Application Shell

### Persistent shell

- Organization name and switcher are visible at the top of navigation.
- Primary navigation uses familiar icons and short text labels.
- Environment or demo status is visible but visually secondary.
- Global search searches only resources permitted in the active organization.
- Notifications link to a specific case, review, action, or setup problem.
- User menu exposes role, profile, organization settings when permitted, and sign out.

### Responsive behavior

- Desktop uses a stable side navigation and a content area optimized for repeated operational work.
- Tablet may collapse secondary panels but preserves the decision summary and primary action.
- Mobile uses a navigation drawer and stacked case sections.
- Critical approval facts and decision controls must not depend on hover or a wide viewport.

## 6. Onboarding And Workspace Activation

The onboarding experience is a resumable checklist, not a marketing wizard.

Required steps:

1. Confirm organization details.
2. Invite or skip additional team members.
3. Add policies or load clearly labeled sample policies.
4. Connect a case source or choose demo cases.
5. Connect an action target or choose the simulator.
6. Configure a basic approval rule.
7. Run one configuration test case.
8. Activate the workspace.

Each step shows:

- why the information is needed;
- current status;
- validation result;
- whether it can be skipped;
- the consequence of skipping it.

Credentials are requested only when a user deliberately configures a real connection. A complete demo
workspace must be usable without credentials.

## 7. Cases

### Case Queue

Purpose: identify and prioritize work.

Default columns:

- Case ID.
- Customer.
- Issue.
- Status.
- Owner.
- Urgency.
- Risk.
- Time remaining.
- Updated time.

Default views:

- My cases.
- Unassigned.
- Needs information.
- Waiting for review.
- In progress.
- At risk.
- Completed.

The queue supports search, filters, sorting, saved views, pagination, assignment, and bulk assignment.
Bulk approval or bulk consequential action is not part of the MVP.

Every status label must describe the business state. Use `Needs review`, not `Approval pending node`;
use `Waiting for customer`, not `Blocked by missing context`.

### Case Workspace

Purpose: understand one case and move it to the next valid state.

Desktop structure:

- **Header:** case ID, issue, status, owner, urgency, SLA, and next valid action.
- **Main column:** conversation, case summary, suggested resolution, response draft, and activity.
- **Context panel:** customer, connected business records, relevant policies, evidence, and risk checks.

Mobile structure:

- Summary and next action first.
- Conversation and suggested resolution second.
- Customer context, evidence, policy, and history as labeled sections or tabs.

Required sections:

1. **Customer request:** original communication and channel.
2. **Case summary:** editable plain-language summary with source freshness.
3. **Customer and business context:** generic records with scenario-specific labels.
4. **Relevant policy:** applicable clauses, source, version, and effective date.
5. **Information needed:** facts required before a safe recommendation can be made.
6. **Suggested resolution:** outcome, rationale, confidence, uncertainty, and proposed actions.
7. **Response draft:** customer-facing text that remains editable and separately reviewable.
8. **Activity:** attributable business events in chronological order.

Primary actions are state-dependent:

- Assign to me.
- Request information.
- Revise resolution.
- Submit for review.
- Complete without external action.
- Execute approved action.
- Escalate.

The interface must never display approval or execution controls when the backend does not authorize
them.

## 8. Reviews

### Review Queue

Purpose: show decisions that require an authorized reviewer.

Priority signals:

- financial or account impact;
- SLA remaining;
- customer risk;
- policy conflict;
- recommendation uncertainty;
- time waiting for review.

### Review Workspace

Purpose: answer, "What exactly am I authorizing, based on which evidence?"

Required review snapshot:

- customer request and relevant context;
- proposed resolution and each proposed action;
- financial or account impact;
- policy evidence and version;
- deterministic risk checks;
- missing or conflicting information;
- recommendation uncertainty;
- proposal, case, evidence, and rule versions;
- submitter identity and submission time.

Decision commands:

- **Approve:** requires confirmation of the exact action and expected outcome.
- **Request changes:** requires an actionable reason and returns ownership to the specialist.
- **Reject:** requires a business reason and does not silently close the customer case.
- **Escalate:** selects an escalation destination and reason.

If the snapshot becomes stale, the review is blocked and the user is directed to inspect the changed
facts. The UI must not offer a one-click override for stale evidence.

## 9. Actions And Recovery

### Action Center

Purpose: monitor approved changes across external systems.

Views:

- Ready to execute.
- In progress.
- Completed.
- Failed safely.
- Outcome unknown.
- Recovery required.

### Action Detail

Required content:

- source case and approved proposal;
- action type and human-readable parameters;
- executing identity and authority;
- target connection;
- idempotency reference;
- attempts and timestamps;
- known external receipt;
- expected and observed outcomes;
- safe next steps.

An `Outcome unknown` state must use high-visibility warning treatment and must not offer a blind retry.
Permitted next steps are inspect provider status, reconcile, mark verified with evidence, or escalate.

## 10. Policy Library

### Policy List

Shows title, status, version, owner, applicability, effective date, last review, and usage health.

Statuses:

- Draft.
- In review.
- Published.
- Scheduled.
- Retired.

### Policy Detail

Supports:

- source document and metadata;
- version history;
- applicability rules;
- extracted clauses and citations;
- review and publish commands;
- cases that used the version;
- warnings for expired, conflicting, or unused policy.

Publishing is a governed command. Editing a published policy creates a new draft version rather than
changing historical evidence.

## 11. Quality And Operational Reporting

The default dashboard answers operational questions instead of advertising AI activity.

Core measures:

- open and at-risk cases;
- median time to decision and resolution;
- cases waiting for review;
- recommendation acceptance and revision rate;
- cases without applicable policy evidence;
- reopened cases;
- action success, safe failure, and outcome-unknown rates;
- recovery time for outcome-unknown actions.

Every chart or summary links to the filtered case set behind it. Model call count, token usage, traces,
and provider latency belong in administrator diagnostics, not the primary operations dashboard.

## 12. Connections, Team, And Settings

### Connections

Each connection card shows:

- system name and purpose;
- read and write capabilities;
- connection health and last successful check;
- affected case or action types;
- credential owner and last rotation where available;
- test, reauthorize, disable, and remove commands.

Removal must explain the effect on active cases and historical records.

The first connected workflow uses a Gmail test inbox. Its normal UI describes two capabilities:
**Read conversations** and **Create drafts**. It must state plainly that the application exposes no
send command while Google's draft-management consent technically permits sending. Connection setup,
imported-conversation states, stale-review behavior, and draft delivery are defined in
`docs/product/CONNECTED_WORKFLOW_CONTRACT.md`.

### Team

Supports invitation, role assignment, status, last active time, and deactivation. Authority changes are
audited and take effect server-side.

### Settings

Contains organization profile, locale and time zone, approval rules, security, retention, redaction,
and notification preferences. Technical runtime settings are separated from business rules.

## 13. Generic Scenario Presentation

The shared Case Workspace remains stable while scenario templates supply meaningful context.

| Template | Business context | Example actions |
| --- | --- | --- |
| Billing dispute | Invoice, charge, payment method, billing period | Reverse charge, grant credit, explain charge |
| Refund request | Purchase, fulfillment, payment, refund history | Full refund, partial refund, credit, reject |
| Account recovery | Account status, verification evidence, recent changes | Unlock, reset access, request verification, escalate |

A template may rename `Business context` to a more useful label such as `Invoice`, `Order`, or
`Account`. It must not change the shared case lifecycle, evidence rules, review semantics, or audit
contract.

## 14. System States

Every data-bearing page defines these states:

- **Loading:** preserve stable layout and announce progress without blocking unrelated navigation.
- **Empty first use:** explain the missing setup and provide one primary next action.
- **Empty result:** preserve filters and provide a clear reset command.
- **Partial data:** show available facts and label unavailable or stale sources.
- **Permission denied:** explain which role or approval is required without exposing restricted data.
- **Connection failure:** identify the affected source and retain the last known snapshot with age.
- **Conflict:** stop the command, show what changed, and require review of current data.
- **Safe failure:** explain that no external change occurred and whether retry is permitted.
- **Outcome unknown:** prohibit blind retry and direct the user to reconciliation.
- **Success:** show the verified outcome and the next business step.

Errors must preserve user-entered drafts whenever possible.

## 15. Plain-Language Rules

- Prefer short business verbs: `Review`, `Approve`, `Request changes`, `Run action`, `Reconcile`.
- Do not expose `RAG`, `LLM`, `tool`, `node`, `checkpoint`, `payload`, or `provider error` in normal
  operations screens.
- Explain why a command is unavailable and what resolves it.
- Confidence never appears alone; pair it with evidence, uncertainty, and missing information.
- Do not use color as the only status signal.
- Destructive or consequential confirmations name the exact object and expected effect.
- Avoid duplicate confirmation pages when no new decision or authority is introduced.
- Do not display fake controls for future features. Use realistic empty states or omit the feature.

## 16. Accessibility And Interaction

- Full keyboard access for navigation, queue operations, review, and dialogs.
- Visible focus indicators and logical focus order.
- Programmatic labels for icon-only controls and status changes.
- Semantic headings, tables, forms, and live regions.
- Text and controls meet WCAG AA contrast targets.
- Touch targets remain usable on mobile.
- Long IDs, customer names, policy titles, and translations do not overlap controls.
- Dates display in the workspace locale with an accessible exact timestamp.
- Money always includes currency and does not rely on locale inference alone.

## 17. Migration From The Current UI

| Current surface | Target surface | Decision |
| --- | --- | --- |
| Case Inbox under `/tasks` | Cases under `/cases` | Rename and generalize contract |
| Task Workspace | Case Workspace | Preserve evidence-first structure |
| Approval page nested under task | Review Workspace under `/reviews` | Make supervisor queue first-class |
| Agent Run Timeline | Activity within Case and diagnostics | Hide technical detail by default |
| Technical Evidence | Quality plus admin diagnostics | Separate business quality from engineering proof |
| Travel booking context | Typed Business Context | Remove from generic required fields |
| Refund-only action | Configured Action | Keep as one template action |
| Demo data sidebar note | Workspace environment status | Preserve honesty, improve placement |

Compatibility aliases may exist temporarily in code and API migrations, but they must not appear in
new UI copy or become permanent product concepts.

## 18. UX Acceptance Criteria

The UX redesign is ready for implementation planning when:

- every primary role has a clear default home and permitted commands;
- the navigation supports case work, reviews, actions, policies, quality, and administration without
  presenting a full helpdesk replacement;
- billing, refund, and account-recovery cases fit the same lifecycle;
- no default screen requires travel-only terminology or fields;
- each primary page has loading, empty, error, permission, and conflict behavior;
- review screens show the complete immutable decision snapshot;
- action recovery distinguishes safe failure from outcome unknown;
- onboarding works with demo data before credentials are supplied;
- normal UI copy uses business language rather than AI infrastructure terms;
- mobile layouts preserve the decision summary, evidence access, and safe primary action.

## 19. Next Design Deliverables

After approval of this contract, produce in order:

1. Route and component inventory mapped from the current frontend.
2. Low-fidelity flow maps for onboarding, case resolution, review, and action recovery.
3. Page-level wireframes and content specifications.
4. Generic fixture contract for the three scenario templates.
5. Frontend migration sprint plan.

Visual styling and implementation begin only after the flows and page responsibilities are stable.
