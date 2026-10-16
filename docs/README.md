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

- [Case Resolution V2 measurement contract and Phase 0 audit](evidence/case-resolution-v2/CONTRACT.md)
- [V2 Phase 0 learning checkpoint](learning/case-resolution-v2/PHASE-0.md)
- [V2 Phase 5 learning checkpoint](learning/case-resolution-v2/PHASE-5.md)
- [V2 Phase 6 learning checkpoint](learning/case-resolution-v2/PHASE-6.md)
- [V2 Phase 8 learning checkpoint](learning/case-resolution-v2/PHASE-8.md)
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
- [AWS-ready deployment architecture](architecture/AWS_READY_DEPLOYMENT.md)
- [Orchestrator framework boundary](architecture/ORCHESTRATOR_FRAMEWORKS.md)
- [Bounded live framework validation](evidence/framework-validation.md)
- [Frontend-backend handoff](frontend/BACKEND_HANDOFF_CONTRACT.md)

## Performance And Delivery

- [Full-stack performance boundaries](frontend/PERFORMANCE_OPTIMIZATION.md)
- [Optional development containers](development/CONTAINERS.md)
- [Database migrations](runbooks/DATABASE_MIGRATIONS.md)
- [Authentication activation](runbooks/AUTHENTICATION_ACTIVATION.md)
- [Provider activation](runbooks/PROVIDER_ACTIVATION.md)
- [Connected Inbox and RAG V2 activation](runbooks/CONNECTED_INBOX_AND_RAG_V2_ACTIVATION.md)
- [Post-environment verification](runbooks/POST_ENV_VERIFICATION.md)
- [Deployment and rollback](runbooks/DEPLOYMENT_AND_ROLLBACK.md)
- [AWS deployment operations](runbooks/AWS_DEPLOYMENT_OPERATIONS.md)

## Security And Operations

- [Security hardening](runbooks/SECURITY_HARDENING.md)
- [Signed webhook activation](runbooks/SIGNED_WEBHOOK_ACTIVATION.md)
- [Backup and restore](runbooks/BACKUP_AND_RESTORE.md)
- [Incident recovery](runbooks/INCIDENT_RECOVERY.md)
- [Pilot SLO](runbooks/PILOT_SLO.md)
- [Controlled pilot runbook](pilot/PILOT_RUNBOOK.md)

## Portfolio Evidence

- [V2 release and evidence index](evidence/case-resolution-v2/README.md)
- [V2 evaluation results](evidence/case-resolution-v2/RESULTS.md)
- [Engineering case study](portfolio/CASE_STUDY.md)
- [Application pack for CV, LinkedIn, Upwork, and interviews](portfolio/APPLICATION_PACK.md)
- [Frozen Governed RAG V2 benchmark](../backend/evaluations/retrieval_v2/README.md)
- [Wave 1 credential-free RAG evaluation](../backend/evaluations/wave1_rag/README.md)
- [Phase 5 Decision and Draft gate](../backend/evaluations/decision_draft/README.md)
- [Phase 6 OpenAI activation evidence](../backend/evaluations/openai_activation/README.md)
- [Case Resolution Evaluation V1](evidence/case-resolution-evaluation-v1/README.md)
- [Current live product tour](evidence/live-product-tour/2026-10-12/README.md)
- [Earlier hosted product walkthrough](evidence/production-demo/README.md)
- [Hosted deterministic workflow acceptance](evidence/hosted-e2e-acceptance/2026-08-05/README.md)
- [Hosted connected Gmail draft acceptance](evidence/hosted-connected-draft-acceptance/2026-08-23/README.md)
- [Developer-operated decision readiness benchmark](evidence/developer-workflow-benchmark/README.md)
- [V2 Phase 5 workflow benchmark reuse](evidence/case-resolution-v2/PHASE5_BENCHMARK_REUSE.md)
- [V2 Phase 6 controlled demo release](evidence/case-resolution-v2/PHASE6_RELEASE.md)

The screenshot evidence from 2026-08-05 predates the repository reconstruction and records the
predecessor hosted deployment of the same product. The 2026-08-23 connected-draft record tests the
current repository revision and is intentionally textual to avoid retaining connected-inbox
identifiers. Historical screenshots are not proof for a new code revision.

## Naming Compatibility

The product name is **Case Resolution Copilot**. Existing deployment environment variables and some
hosted project URLs retain the `SUPPORT_COPILOT_*` or `ai-support-escalation-copilot` identifiers to
avoid unnecessary secret rotation and deployment migration. Those identifiers are compatibility
details, not the product name or a second runtime.
