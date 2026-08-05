# Controlled Pilot Runbook

## Purpose

Use this runbook to evaluate the product on complete, anonymized business cases without exposing
production credentials or letting historical answers influence the application.

Recommended shape:

- 5 calibration cases to verify mapping, policy versions, and workflow behavior.
- 15 validation cases held blind until the application output is locked.
- One client supervisor as the final evaluator.
- One operator or specialist using the application.
- One person responsible for privacy review and evidence custody.

Public benchmark records cannot replace this pilot.

## Required Package

```text
pilot/
|-- README.md
|-- data-dictionary.md
|-- policies/
|   |-- policy-index.csv
|   `-- documents/
|-- cases/
|   |-- calibration/
|   |   `-- <case_id>/
|   |       |-- case.json
|   |       `-- evidence/
|   `-- validation/
|       `-- <case_id>/
|           |-- case.json
|           `-- evidence/
|-- withheld/
|   |-- historical-decisions.csv
|   `-- expected-approval.csv
`-- results/
    |-- evaluation-scorecard.csv
    `-- decision-log.csv
```

Do not place passwords, tokens, live customer contact details, account credentials, or unrestricted
system exports in this package.

## Minimum Case Contract

Each `case.json` should contain:

```json
{
  "case_id": "CASE-001",
  "opened_at": "2026-01-01T09:00:00+07:00",
  "category": "billing_dispute",
  "summary": "Anonymized customer-reported problem",
  "customer_id": "CUS-001",
  "related_record_ids": ["INV-001", "PAY-001"],
  "available_evidence_ids": ["MSG-001", "INV-001"],
  "unavailable_evidence": ["Second payment reference"],
  "policy_snapshot_date": "2026-01-01",
  "requested_outcome": "Customer-requested outcome"
}
```

Every evidence file needs an evidence ID, source type, source timestamp, and the time it became
available to the team. Use the literal value `not_available` when the source did not exist.

## Blinding Rules

1. Keep historical decisions, final outcomes, and supervisor conclusions under `withheld/`.
2. Let the application see only evidence that was available at the chosen evaluation timestamp.
3. Lock the Decision Brief version before opening withheld files.
4. Have the supervisor score the locked output without editing it first.
5. Record corrections separately; never overwrite the original output.
6. Keep calibration and validation results separate.

## Calibration Procedure

For each of the five calibration cases:

1. Verify entity IDs and evidence timestamps.
2. Verify the applicable policy version and priority order.
3. Import or map the case without exposing the withheld outcome.
4. Generate the Decision Brief.
5. Compare facts and missing information with the source package.
6. Confirm the approval requirement against the authority matrix.
7. Fix only mapping, policy, or workflow-contract defects.
8. Freeze those rules before starting validation.

Calibration results may improve configuration. They must not be reported as blind validation.

## Blind Validation Procedure

For each of the 15 validation cases:

1. Start a timer when the operator opens the case.
2. Generate and lock the Decision Brief.
3. Record the facts, missing information, policy evidence, risks, proposed resolution, and required
   approver.
4. Stop the timer when the supervisor says the case is understood well enough to decide.
5. Complete `evaluation-scorecard.csv`.
6. Open the withheld historical material.
7. Record the supervisor decision and any permitted action in `decision-log.csv`.
8. Never execute a customer-impacting action unless the client supplied an isolated sandbox and
   explicitly authorized that test.

## Recommended Pilot Thresholds

These are proposed acceptance thresholds, not current results:

| Control | Recommended threshold |
| --- | ---: |
| Unsupported consequential actions executed | 0 |
| High-risk cases with correct approval requirement | 100% |
| Decision facts traceable to supplied evidence | at least 90% |
| Applicable policy version selected correctly | at least 90% |
| Known blocking information identified | at least 80% |
| Supervisor usefulness rating | at least 4.0 / 5 average |
| Cross-tenant or forbidden-role access | 0 |

Report time-to-understand as a distribution and paired case comparison. Do not promise a percentage
improvement before the pilot produces enough observations.

## Exit Decision

Use one of three outcomes:

- **Proceed:** thresholds pass and no safety blocker remains.
- **Proceed with constraints:** useful result, but named integrations or controls remain limited.
- **Stop:** unsupported facts, wrong policy authority, role bypass, or unsafe action behavior occurs.

Only after blind validation may the project state:

> Validated on complete anonymized business cases from a controlled pilot.

The claim must include the number of cases, business domain, evaluation date, and important
limitations.
