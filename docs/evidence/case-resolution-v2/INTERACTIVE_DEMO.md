# V2 interactive walkthrough

The walkthrough uses the existing authenticated Vercel application and database. Manual work stays in a separate, static local workspace. Three fresh scenarios demonstrate the V2 controls:

1. **Verified resolution:** prepare a cited Decision Brief, submit and approve its frozen snapshot, execute a synthetic refund, independently read back the target, close with a simulated communication reference, then reopen with new evidence.
2. **SOP revision:** approve against revision 1, publish revision 2, observe the old action being blocked, publish a rollback as revision 3, and confirm that rollback does not revive the old approval.
3. **Uncertain outcome:** the target commits a synthetic refund and times out. Repeated execution is blocked. Reconciliation through a fresh gateway instance finds the original operation and exactly one effect.

## Boundaries

- Each session gets a new synthetic tenant, case, policy, and target. Existing cases, policies, identities and connection settings are not modified.
- Entry requires a real authenticated administrator. Session access is bound to that administrator and their original workspace. The browser switches explicitly labelled **simulated** specialist, reviewer and policy-manager roles inside that synthetic tenant only. These identities cannot sign in.
- Commands use the existing product services/routes, including review separation, snapshot freshness, execution authorization, version checks, verification and closure rules. No shared application state or normal authentication dependency is overridden.
- Synthetic target objects and effects are persisted as append-only database events, separately from action receipts. Advisory locks serialize target mutations. A new request can reconstruct and read back the same object without an in-memory outcome cache. The database must have the existing V2 lifecycle migration `20261013_0025`; the walkthrough adds no new migration, database, or credentials.
- The scope has no payment network, Gmail delivery or real customer changes. A communication reference is an operator attestation to a simulated message, not proof of external email delivery.
- This is a single-operator functional demonstration. It is not an independent two-person review study, held-out timing benchmark, real-payment test, or evidence of production provider reliability. Existing historical benchmark claims retain their original scope.

## Validation and handoff

Lightweight source checks run locally without loading `.env`. PostgreSQL integration tests run only on disposable CI infrastructure. The PR must pass the existing required quality gate and the dedicated V2 integration job before merge. Production uses the existing Vercel projects. Agent smoke sessions are separate from fresh user sessions.

Deployment preflight must verify both the application revision and database migration head. A successful build does not apply database migrations. Session creation rejects a missing lifecycle table before writing new demo data; apply the repository's guarded migration procedure against the selected existing database, then resume the same creation request.

The pack has three manual scenarios and three assisted counterparts; stopwatch measurement is optional and requires a separate matched study protocol before making a comparative CV claim. Start with [the operator instructions](operator-demo/START-HERE.md).
