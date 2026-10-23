# Functional validation checklist

Keep agent smoke traces separate from operator traces. Use a fresh session for every scenario. The normal workspace's case/policy records and real memberships must remain unchanged.

| Check | Required evidence |
| --- | --- |
| Access boundary | Signed-out access denied; non-administrator denied; another administrator's session inaccessible; arbitrary tenant/case identifiers rejected |
| Frozen authority | Proposal version, source/evidence IDs, policy revision, review snapshot fingerprint, reviewer identity and reason are visible |
| Role boundary | Specialist execution denied; the simulator does not change the signed-in user's actual membership |
| Consequential action | Exact registered target, original recipient, amount, currency and reason code match the approved payload |
| Verification | A fresh gateway reads the database target ledger; operation identity matches; effect count is one; product `action_verified` event exists |
| Closure | A receipt alone cannot close; unknown outcome cannot close; verified closure records simulated communication attestation |
| Reopen | New evidence reference is present; reopened event links the previous completion ID |
| SOP revisions | v2 and rollback v3 are dated immutable revisions; execution under the old approval is blocked after each; target effect count remains zero |
| Timeout recovery | Initial attempt yields `outcome_unknown`; repeat execution is blocked; reload/reconciliation finds the same operation; one attempt and one effect; verified closure succeeds |
| Trace export | Export contains the current synthetic case, policy revisions, review/action details, target ledger, lifecycle and command outcomes |

Manual results are operator-authored records, not automatically scored policy decisions. Inspect their notes and history against the same scenario goals. A manual record labelled `verified` is not itself evidence of correctness; compare it with the read-back and approved payload.

The automated integration job exercises real product commands on disposable PostgreSQL. Local validation is limited to source/type/unit checks. The browser walkthrough checks the existing deployed app with synthetic sessions only. No production database reset, new host, Docker/WSL on the operator laptop, or secret access is required.
