# Frontend Usability Review

Original review: 30 July 2026. The reconstructed source retains these controls and re-runs their
component, accessibility, lint, and type checks; this document is still not user research.

## Method And Constraint

This review uses code inspection, component tests, schema tests, linting, and TypeScript. It is an
engineering review, not user research. Local browser automation, visual-regression loops, local
Next.js servers, load tests, and extra watch processes remain excluded by the resource policy. One
bounded hosted-browser release pass is allowed after deployment; formal real-user acceptance remains
separate and is defined in `USABILITY_STUDY_PROTOCOL.md`.

## Workflow Walkthroughs

### Specialist

1. Find and filter work in Cases.
2. Assign an unowned case in the preview.
3. Inspect facts, missing information, evidence, risk, and source freshness.
4. Save a response draft and submit a proposal for review.
5. Monitor an approved action and use the allowed recovery path.

Accepted: Cases use generic business language, preserve URL state, expose stale source data, and do not
claim that preview commands changed an external system.

### Supervisor

1. Prioritize Reviews by impact, wait time, uncertainty, policy state, and freshness.
2. Open an immutable proposal snapshot.
3. Reserve the review and provide an attributable reason.
4. Approve, request changes, reject, or escalate.
5. Hard-stop stale or externally reserved snapshots.

Accepted: Cases and Reviews have different questions, columns, controls, and authority semantics.

### Administrator

1. Inspect policy lifecycle and immutable historical versions.
2. Create a draft from a published policy.
3. Inspect connection capabilities and health without exposing secrets.
4. Review team roles and authority.
5. Configure organization, approval, notification, security, and retention defaults.

Accepted: Every available command has a visible control or receipt. Published policy evidence remains
version-bound.

### Auditor

1. Inspect Quality metrics and evaluated decision evidence.
2. Follow case and policy-version references.
3. Open restricted diagnostics as a secondary view.

Accepted: Quality leads with business evidence; technical diagnostics no longer define the primary
product surface.

## Issues Closed

- Removed dead organization, search, notification, user-menu, attachment, and case-more controls.
- Added global focus-visible styling, reduced-motion handling, pointer affordances, and semantic status
  regions.
- Added connection dialog focus entry, Escape handling, and focus restoration.
- Added a shared focus trap, body-scroll lock, Escape handling, and focus restoration for the
  connection drawer and mobile navigation.
- Added arrow, Home, and End keyboard behavior with complete tab/panel relationships in the Case
  Workspace and conversation composer.
- Enforced one `main` landmark per protected page and retained a keyboard skip link.
- Added generic loading, recoverable error, and not-found states.
- Added horizontal overflow for dense tables and responsive single-column fallbacks for workspaces.
- Added explicit text and icons so risk, state, and authority never depend on color alone.
- Replaced normal-workflow technical AI language with case, evidence, policy, review, and outcome terms.
- Replaced visible `proposal`, `target`, and `policy evidence` labels with recommended resolution,
  connected system, and policy guidance where the technical terms did not add decision value.
- Kept all consequential demo actions explicitly labeled as previews until backend receipts exist.

## Remaining Usability Debt

- The post-deployment hosted-browser pass is still required at desktop and mobile widths.
- Zoomed and forced-colors visual review remains manual.
- Screen-reader walkthroughs with NVDA or VoiceOver are not yet performed.
- The formal usability study is planned but has not been run.
- Real localization review is pending translated strings and locale-specific content expansion.
- Live role routing is active, but the deployed review and action queues do not yet provide a
  reversible consequential journey for final Supervisor acceptance.
- Final user acceptance of terminology and workflow clarity remains open until the study is run.
