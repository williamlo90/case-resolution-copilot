# Hosted connected draft acceptance - 2026-08-23

## Verdict

The hosted connected workflow passed one bounded synthetic acceptance journey:

1. An imported Gmail case was enriched with two checked payment records.
2. The decision brief retrieved current billing policy guidance and reported no blocking information gap.
3. The case moved from `new` to `investigating`; the earlier brief became ineligible for review until it was refreshed.
4. An administrator submitted the refreshed proposal and was prevented from reviewing their own work.
5. A specialist could inspect the review but received no reserve or decision controls.
6. A different supervisor reserved and approved the exact proposal snapshot with an attributable reason.
7. Approval materialized response draft version 3 as `ready`.
8. The connected Gmail adapter created one draft. A fresh page load preserved `Draft ready`, removed the create command, and confirmed that nothing was sent automatically.

This is controlled engineering evidence using an allowlisted synthetic email thread. It is not a
claim of validation on complete real-business cases, production readiness at arbitrary scale, or
measured customer impact.

## Environment

| Component | Acceptance environment |
| --- | --- |
| Frontend | Hosted Next.js production deployment on Vercel |
| Backend | Hosted FastAPI production deployment on Vercel |
| Database | Connected Neon Postgres environment |
| Identity | Clerk development instance with separate administrator, specialist, and supervisor sessions |
| Policy retrieval | Bounded governed V1 hybrid retrieval |
| Decision wording | Hosted AI-assisted path; provider token and latency metrics were not captured in this journey |
| Connected provider | Gmail draft API with no automatic send operation |
| Test data | Explicitly labeled synthetic allowlisted thread and payment fixtures |

## Traceable record chain

| Record | Identifier |
| --- | --- |
| Case | `CS-EMAIL-FC67D7539E5D` |
| Resolution proposal | `PRP-F904AAEB81B0DA13` version 4 |
| Review | `RV-87DDC33777FC5055` |
| Proposed action | `PRA-99E6720825DF8FF3` |
| Response draft | Version 3, status `ready` |
| Payment evidence | `PAY-CRC-001-A`, `PAY-CRC-001-B` |
| Governing policy | `Billing adjustments` |

## Acceptance results

| Check | Result | Observed evidence |
| --- | --- | --- |
| Checked business evidence is visible in the brief | Pass | Two settled USD 49 payment records and their source references were displayed |
| Current policy supports the recommendation | Pass | The published duplicate-charge clause appeared in Relevant policies |
| Missing information is fail-closed | Pass | The second payment gap disappeared only after both records existed |
| New case has an explicit investigation path | Pass | `Start investigation` moved the case to `Investigating` |
| Stale brief cannot be submitted | Pass | Submit stayed disabled after the case version changed and enabled only after refresh |
| Submitter cannot self-review | Pass | Reservation was denied with a separation-of-duties message |
| Specialist cannot mutate reviews | Pass | The specialist view exposed inspection only |
| Supervisor approval is attributable | Pass | A different supervisor reserved and approved the exact snapshot with a reason |
| Approval materializes immutable response content | Pass | The case showed response draft version 3 as `ready` |
| Gmail write-back remains draft-only | Pass | UI reported `Gmail draft created. Nothing was sent automatically.` |
| Repeat UI creation is unavailable | Pass | After reload, `Draft ready` persisted and the create button was absent |

The hosted journey observed one create operation and the persisted replay guard. The stronger claim
that provider replay creates exactly one remote draft is additionally covered by service-level
idempotency tests; this journey deliberately did not issue a second provider write.

## Defects found and corrected

| Defect | Correction | Revision |
| --- | --- | --- |
| Imported duplicate-charge wording scored below the deterministic vector threshold | Added bounded lexical scoring alongside vector scoring without lowering the relevance threshold | `6ea2191` |
| A `new` case had no visible path into investigation and a changed case could expose stale submit eligibility | Added `start_investigation`, preserved both valid next steps, and bound submit eligibility to the brief's case version | `54c023b` |
| Review detail discarded source snapshot fields and failed domain validation | Mapped the complete API business-context contract and added a transport regression test | `54fb762` |

## Verification performed

- Backend unit and contract suite: `404` passed.
- Backend Ruff: passed.
- Backend strict Mypy: passed across `403` source files.
- Frontend full suite before the final hosted defects: `53` files and `170` tests passed serially.
- Focused workflow and command regression set: `30` passed.
- Review transport regression: `1` passed.
- Six-case benchmark fixture and answer-leakage validation: `10` passed; no timed run was executed.
- Frontend TypeScript and ESLint: passed after the final adapter correction.
- Vercel frontend and backend releases for the tested revisions reached `Ready`.

## Evidence handling

No screenshot was retained for this journey because the connected test inbox surfaces account and
email identifiers. The record intentionally keeps only synthetic case, review, proposal, evidence,
and revision identifiers. Passwords, OAuth codes, tokens, API keys, raw credentials, and customer
email addresses are not included.

## Residual work

- Run the six-case timed operator benchmark and its manual baseline before claiming measured time savings.
- Measure warm authenticated LCP with the agreed bounded browser scenario.
- Exercise hosted disconnect, reconnect, expiry, rate-limit, timeout, and ambiguous-provider recovery paths.
- Run the planned usability study before claiming that operators find the terminology intuitive.
- The source case continues to display `Needs review` after approval while the unsent external draft remains pending. The immutable review and Gmail authorization are correct, but the label is a non-blocking usability gap.
