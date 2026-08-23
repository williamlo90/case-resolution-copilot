# Case Resolution Copilot Documentation

The root [README](../README.md) is the portfolio-oriented product overview. This index points to the
contracts and operating material used to build and evaluate the application.

## Product And UX

- [Product contract](product/PRODUCT_CONTRACT.md)
- [UX architecture](product/UX_ARCHITECTURE.md)
- [Connected decision workflow contract](product/CONNECTED_WORKFLOW_CONTRACT.md)
- [Frontend usability review](frontend/USABILITY_REVIEW.md)
- [Planned usability study](frontend/USABILITY_STUDY_PROTOCOL.md)

## Architecture And Contracts

- [Architecture decisions](adr/README.md)
- [API conventions](api/CONVENTIONS.md)
- [Generic SaaS backend contract](backend/GENERIC_SAAS_CONTRACT.md)
- [Identity and RBAC](backend/IDENTITY_AND_RBAC.md)
- [Generic cases](backend/GENERIC_CASES.md)
- [Connected inbox architecture](backend/CONNECTED_INBOX_ARCHITECTURE.md)
- [Policy governance](backend/POLICY_GOVERNANCE.md)
- [Governed Policy RAG V2](backend/GOVERNED_RAG_V2.md)
- [Decision Briefs](backend/DECISION_BRIEFS.md)
- [Reviews](backend/REVIEWS.md)
- [Actions and connections](backend/ACTIONS_AND_CONNECTIONS.md)
- [Operational controls](backend/OPERATIONAL_CONTROLS.md)
- [Evaluation strategy](backend/EVALUATION_STRATEGY.md)
- [Frontend-backend handoff](frontend/BACKEND_HANDOFF_CONTRACT.md)

## Performance And Delivery

- [Connected workflow SDLC and canonical phase map](development/CONNECTED_WORKFLOW_SDLC.md)
- [Full-stack performance boundaries](frontend/PERFORMANCE_OPTIMIZATION.md)
- [Optional development containers](development/CONTAINERS.md)
- [Database migrations](runbooks/DATABASE_MIGRATIONS.md)
- [Authentication activation](runbooks/AUTHENTICATION_ACTIVATION.md)
- [Provider activation](runbooks/PROVIDER_ACTIVATION.md)
- [Connected Inbox and RAG V2 activation](runbooks/CONNECTED_INBOX_AND_RAG_V2_ACTIVATION.md)
- [Post-environment verification](runbooks/POST_ENV_VERIFICATION.md)
- [Deployment and rollback](runbooks/DEPLOYMENT_AND_ROLLBACK.md)

## Security And Operations

- [Security hardening](runbooks/SECURITY_HARDENING.md)
- [Signed webhook activation](runbooks/SIGNED_WEBHOOK_ACTIVATION.md)
- [Backup and restore](runbooks/BACKUP_AND_RESTORE.md)
- [Incident recovery](runbooks/INCIDENT_RECOVERY.md)
- [Pilot SLO](runbooks/PILOT_SLO.md)
- [Controlled pilot runbook](pilot/PILOT_RUNBOOK.md)

## Portfolio Evidence

- [Engineering case study](portfolio/CASE_STUDY.md)
- [Three-minute demo](portfolio/DEMO_SCRIPT.md)
- [Frozen Governed RAG V2 benchmark](../backend/evaluations/retrieval_v2/README.md)
- [Phase 5 Decision and Draft gate](../backend/evaluations/decision_draft/README.md)
- [Phase 6 OpenAI activation evidence](../backend/evaluations/openai_activation/README.md)
- [Hosted product walkthrough](evidence/production-demo/README.md)
- [Hosted deterministic workflow acceptance](evidence/hosted-e2e-acceptance/2026-08-05/README.md)
- [Developer-operated decision readiness benchmark](evidence/developer-workflow-benchmark/README.md)

The screenshot evidence predates the repository reconstruction and records the predecessor hosted
deployment of the same product. Current-source verification and historical hosted product evidence
must be reported separately; historical screenshots are not proof for a new code revision.

## Naming Compatibility

The product name is **Case Resolution Copilot**. Existing deployment environment variables and some
hosted project URLs retain the `SUPPORT_COPILOT_*` or `ai-support-escalation-copilot` identifiers to
avoid unnecessary secret rotation and deployment migration. Those identifiers are compatibility
details, not the product name or a second runtime.
