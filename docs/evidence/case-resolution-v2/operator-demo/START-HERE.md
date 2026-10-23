# V2 walkthrough pack

**Manual: local static workspace. Assisted: existing Vercel app, **Cases / Reviews / Actions / Policies**.**

There are **3 scenarios × 2 modes = 6 tasks**. Start with scenario 1 only. There is no need to finish all tasks in one sitting.

| Scenario | What to demonstrate | Evidence to save |
| --- | --- | --- |
| 1. Verified resolution and reopen | Brief → frozen review → approval → action → independent read-back → closure → reopen | One target effect, verified event before closure, reopen linked to the previous completion |
| 2. SOP revision and rollback | Approval under v1 → new v2 cap → old execution blocked → rollback as v3 → old execution still blocked | Dated revisions 1/2/3, two blocked attempts, zero target effects |
| 3. Timeout recovery | Target commits but response is lost → second execution blocked → reload → reconcile original operation → close | Same operation ID, one execution attempt, one effect, verified closure |

## First task: manual scenario 1

1. Open the local manual workspace when the facilitator starts its static server. No Docker, WSL, local application backend, or database is needed.
2. Choose **1 · Verified resolution & reopen**. Read the task, source record and SOP.
3. Write your own brief and review record. Switch the labelled simulated role as you record each stage. This is one operator playing roles, not an independent reviewer study.
4. Enter the exact target, original recipient, minor-unit amount, currency and operation ID in the synthetic target console. Apply the approved simulated refund once.
5. Read the target back. Record the verification and a simulated customer-message reference. Record completion, then reopen with a new-evidence reference.
6. Press **Save**, then **Download result**.

The workspace deliberately does not generate decisions or check policy eligibility for you. Its target console validates the registered target/payload and prevents duplicate writes; deciding whether authority is current is your task.

## Assisted counterpart

1. Sign in and open **Cases > Try a practice case**. Choose the matching scenario to create isolated sample records. Saved sessions can be resumed from the same section.
2. Read the request and evidence. Click **Analyze case**, inspect the Decision Brief, then **Submit for review**.
3. Follow **Open review as reviewer**. Reserve the review, enter a reason and approve. The banner names the simulated role on each page; normal account permissions stay unchanged.
4. Open the approved action. Execute once, then **Check target outcome**. A receipt alone does not enable closure. The verification summary shows the amount, confirmation reference and number of recorded changes.
5. Follow **Review evidence and close case**. In **Resolution**, enter a reason and a simulated communication reference such as `SIM-MESSAGE-01`, then close. For scenario 1, reopen with a new reason and evidence reference such as `NEW-EVIDENCE-01`.
6. For the SOP scenario, after approval follow the policy link, publish the USD 100 limit, then inspect the blocked action. Restore the USD 500 limit as a new revision and confirm the old approval remains blocked. No refund should execute.
7. For the timeout scenario, execute once and observe **Outcome uncertain**. Reload the page, then **Check target outcome**. The original refund should be verified with one recorded change; close from the case.

Use the existing product screens throughout. The former technical `/demo/v2` page redirects to Cases. References attest to simulated communication and do not send Gmail. Save screenshots of the result and the practice case URL for review; session history persists in the existing database.

## Terms

- **Minor units:** USD 240.00 is `24000` cents.
- **Receipt:** the target acknowledged a request; this alone is insufficient for closure.
- **Read-back / reconciliation:** look up the original operation and verify the current target result without issuing the action again.
- **Snapshot:** the exact proposal, evidence and policy authority that the reviewer approved.
- **Rollback:** publish the previous rule content as a new revision. It does not restore an old approval.

## Scope of results

This pack demonstrates V2 functionality. Optional stopwatch observations are exploratory: the repeated scenario content and single-operator role simulation do not constitute a held-out controlled timing comparison. Historical benchmark evidence retains its original scope.

A facilitator reviews the saved result against the scenario goals above. Keep operator screenshots and manual downloads local; do not commit them by default.
