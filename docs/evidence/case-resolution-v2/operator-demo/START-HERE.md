# V2 walkthrough pack

**Manual: local static workspace. Assisted: existing Vercel app, `/demo/v2`.**

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

1. Sign in to the existing Case Resolution app and open **V2 demo** in the navigation.
2. Choose the matching scenario and **Create fresh session**. Agent smoke sessions must not be used as your fresh run.
3. Read the visible task and source evidence. As **Specialist**, generate and inspect the Decision Brief, then submit it.
4. Switch to **Reviewer**, reserve the review, supply a reason and approve its snapshot.
5. Follow that scenario's remaining task. For SOP changes, switch to **Policy manager** to publish, then back to Reviewer to attempt execution. For timeout recovery, reload saved state before reconciliation.
6. Inspect the target effect count and lifecycle, then **Download trace**. References such as `SIM-MESSAGE-01` attest to a simulated message; they do not send Gmail.

## Terms

- **Minor units:** USD 240.00 is `24000` cents.
- **Receipt:** the target acknowledged a request; this alone is insufficient for closure.
- **Read-back / reconciliation:** look up the original operation and verify the current target result without issuing the action again.
- **Snapshot:** the exact proposal, evidence and policy authority that the reviewer approved.
- **Rollback:** publish the previous rule content as a new revision. It does not restore an old approval.

## Scope of results

This pack demonstrates V2 functionality. Optional stopwatch observations are exploratory: the repeated scenario content and single-operator role simulation do not constitute a held-out controlled timing comparison. Historical benchmark evidence retains its original scope.

No answer key is shown before the operator completes a task. A facilitator validates the exported evidence against the scenario goals above. Results stay local until reviewed; do not commit operator downloads by default.
