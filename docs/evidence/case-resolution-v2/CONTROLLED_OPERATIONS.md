# Controlled business operations

The deterministic decision engine supports explicit, published operation rules for invoice
address/currency/locale/PO changes, seat credits, course/premium refunds, account renaming,
session revocation and recovery-email changes. All require human review. Existing refund,
duplicate-charge, recovery and service-correction flows remain available.

An operation is selected by the normalized business record's `requested_operation`, and
must match exactly one immutable, effective SOP grant. Free-form policy prose does not
authorize an arbitrary new operation. The source hash, tenant, case, category and effective
interval checks also apply to the executable rule.

Example source for an account rename, published under `account_access`:

````text
Rename an account only with verified naming entitlement, retaining its original owner.

```case-resolution-rules
{"schema_version":1,"rules":[{"kind":"controlled_operation","action_type":"rename_account","max_amount_minor":0,"currency":"USD"}]}
```
````

The normalized business record must supply:

```json
{
  "requested_operation": "rename_account",
  "requested_target": "SYNTHETIC-OBJECT-1",
  "name_entitlement": "verified",
  "requested_new_name": "Synthetic New Name",
  "original_recipient": "SYNTHETIC-OWNER-1",
  "authorized_recipient": "SYNTHETIC-OWNER-1",
  "authorized_reason_code": "documented-entitlement",
  "authorized_access_scope": "same_owner",
  "authorized_preserve_owner": "true"
}
```

These source fields are not an approval. The application still requires an independent
reviewer, an unchanged proposal/evidence/policy snapshot, an eligible connection and current
execution authority. Missing or conflicting values produce an information gap.

Financial operations require integer minor units, a matching case amount/currency and the
published amount ceiling. Identity operations require their fixed scope and owner preservation.
A recovery-email challenge must name the actual requested destination. Target values such as
the new name, address, locale and PO are included in the approved parameters, never invented.

The credential-free demo gateway accepts an explicit `objects` mapping when constructed.
Controlled actions fail before change if the target is absent or owned by another recipient.
The target stores business changes and an operation ledger independently of receipt generation.
Read-back compares the current business object against the recorded effect. A later change
produces mismatch; receipt acknowledgement alone does not verify success. Repeated operation
keys do not reapply the effect, and changed payloads under the same key are rejected.

This is synthetic target behavior. State is in memory in that target process; app-service
reconstruction can retain the same external target instance, but losing the target process
is not durable remote-provider recovery. Production webhook connections do not automatically
gain these operations. No payment, identity provider or real account is modified by these tests.

Validation entry points:

- `tests/unit/test_controlled_operations.py`: all ten decision branches and negative authority,
  amount, category, recipient, scope and input cases.
- `tests/unit/test_controlled_target.py`: ten observable target changes, replay, mismatch and
  fail-before-change cases.
- `tests/integration/test_controlled_operation_api.py`: published SOP → proposal → separate
  reviewer approval → effect followed by timeout → duplicate rejection → read-back for account
  rename and draft-invoice currency.

Phase 4 evaluation remains in progress. These development tests are not a sealed-holdout score.
