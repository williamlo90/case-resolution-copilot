from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import TypeVar

from pydantic import BaseModel

from app.tools.contracts import (
    AccountSnapshotOutput,
    ActionReceiptOutput,
    ActionStatus,
    CaseOutput,
    CreateCreditInput,
    CreditLookupOutput,
    CustomerProfileOutput,
    DraftInput,
    DraftOutput,
    EntitlementInput,
    EntitlementOutput,
    EscalateInput,
    IdentifierInput,
    LookupCreditInput,
    NotifyTeamInput,
    ProviderScenario,
    UpdateCaseStatusInput,
)
from app.tools.errors import (
    ProviderPreSendTimeout,
    ProviderRecordNotFound,
    ProviderRejected,
    ProviderTimeout,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class _StoredAction:
    receipt: ActionReceiptOutput
    visible_after_lookups: int = 0
    lookup_count: int = 0


class DeterministicProviderSimulator:
    """Small stateful support-system simulator with repeatable failure boundaries."""

    def __init__(self) -> None:
        self._cases = {
            "CASE-1042": CaseOutput(
                case_id="CASE-1042",
                account_id="ACCT-218",
                status="waiting_approval",
                category="billing",
                customer_message="I was charged twice for my support plan.",
            )
        }
        self._customers = {
            "CUS-2048": CustomerProfileOutput(
                customer_id="CUS-2048",
                name="Maya Chen",
                tier="vip",
                locale="en-SG",
                contact="maya.chen@example.test",
            )
        }
        self._accounts = {
            "ACCT-218": AccountSnapshotOutput(
                account_id="ACCT-218",
                customer_id="CUS-2048",
                plan="enterprise",
                status="active",
                balance=Decimal("284.00"),
                currency="USD",
            )
        }
        self._actions: dict[str, _StoredAction] = {}

    def get_case(self, request: IdentifierInput) -> CaseOutput:
        return self._copy_or_raise(self._cases, request.id, "Case")

    def get_customer_profile(self, request: IdentifierInput) -> CustomerProfileOutput:
        return self._copy_or_raise(self._customers, request.id, "Customer")

    def get_account_snapshot(self, request: IdentifierInput) -> AccountSnapshotOutput:
        return self._copy_or_raise(self._accounts, request.id, "Account")

    def calculate_entitlement(self, request: EntitlementInput) -> EntitlementOutput:
        account = self.get_account_snapshot(IdentifierInput(id=request.account_id))
        maximum = Decimal("500.00") if account.plan == "enterprise" else Decimal("100.00")
        eligible = request.case_category == "billing" and request.amount <= maximum
        return EntitlementOutput(
            eligible=eligible,
            maximum_credit=maximum,
            reason_code="DUPLICATE_CHARGE" if eligible else "MANUAL_REVIEW_REQUIRED",
        )

    def draft_customer_response(self, request: DraftInput) -> DraftOutput:
        self.get_case(IdentifierInput(id=request.case_id))
        return self._draft("CDR", request)

    def draft_internal_note(self, request: DraftInput) -> DraftOutput:
        self.get_case(IdentifierInput(id=request.case_id))
        return self._draft("NOTE", request)

    def create_credit_request(self, request: CreateCreditInput) -> ActionReceiptOutput:
        account = self.get_account_snapshot(IdentifierInput(id=request.account_id))
        if request.currency != account.currency or request.amount > Decimal("500.00"):
            raise ProviderRejected("Credit amount or currency is outside simulator authority.")
        return self._write(
            resource_id=request.account_id,
            idempotency_key=request.idempotency_key,
            scenario=request.scenario,
            prefix="CRD",
            data={
                "amount": str(request.amount),
                "currency": request.currency,
                "reason_code": request.reason_code,
            },
        )

    def update_case_status(self, request: UpdateCaseStatusInput) -> ActionReceiptOutput:
        case = self.get_case(IdentifierInput(id=request.case_id))
        receipt = self._write(
            resource_id=request.case_id,
            idempotency_key=request.idempotency_key,
            scenario=request.scenario,
            prefix="STS",
            data={"status": request.status},
        )
        case.status = request.status
        return receipt

    def escalate_to_supervisor(self, request: EscalateInput) -> ActionReceiptOutput:
        self.get_case(IdentifierInput(id=request.case_id))
        return self._write(
            resource_id=request.case_id,
            idempotency_key=request.idempotency_key,
            scenario=request.scenario,
            prefix="ESC",
            data={"reason": request.reason},
        )

    def notify_team(self, request: NotifyTeamInput) -> ActionReceiptOutput:
        self.get_case(IdentifierInput(id=request.case_id))
        return self._write(
            resource_id=request.case_id,
            idempotency_key=request.idempotency_key,
            scenario=request.scenario,
            prefix="NTF",
            data={"team": request.team, "message": request.message},
        )

    def lookup_credit(self, request: LookupCreditInput) -> CreditLookupOutput:
        stored = self._find_action(request)
        if stored is None:
            return CreditLookupOutput(found=False)
        stored.lookup_count += 1
        if stored.lookup_count <= stored.visible_after_lookups:
            return CreditLookupOutput(found=False)
        return CreditLookupOutput(found=True, receipt=stored.receipt.model_copy(deep=True))

    def _write(
        self,
        *,
        resource_id: str,
        idempotency_key: str,
        scenario: ProviderScenario,
        prefix: str,
        data: dict[str, str],
    ) -> ActionReceiptOutput:
        existing = self._actions.get(idempotency_key)
        if existing is not None:
            return existing.receipt.model_copy(update={"duplicate": True})
        if scenario is ProviderScenario.REJECT_BEFORE_SIDE_EFFECT:
            raise ProviderRejected()
        if scenario is ProviderScenario.TIMEOUT_BEFORE_SEND:
            raise ProviderPreSendTimeout()
        suffix = sha256(idempotency_key.encode()).hexdigest()[:10].upper()
        receipt = ActionReceiptOutput(
            external_reference=f"{prefix}-{suffix}",
            resource_id=resource_id,
            idempotency_key=idempotency_key,
            status=ActionStatus.PENDING,
            data=data,
        )
        self._actions[idempotency_key] = _StoredAction(
            receipt=receipt,
            visible_after_lookups=(
                2 if scenario is ProviderScenario.DELAYED_POSTCONDITION else 0
            ),
        )
        if scenario is ProviderScenario.TIMEOUT_AFTER_ACCEPTANCE:
            raise ProviderTimeout()
        return receipt.model_copy(deep=True)

    def _find_action(self, request: LookupCreditInput) -> _StoredAction | None:
        if request.idempotency_key is not None:
            stored = self._actions.get(request.idempotency_key)
            if stored and stored.receipt.resource_id == request.account_id:
                return stored
            return None
        return next(
            (
                stored
                for stored in self._actions.values()
                if stored.receipt.external_reference == request.external_reference
                and stored.receipt.resource_id == request.account_id
            ),
            None,
        )

    @staticmethod
    def _draft(prefix: str, request: DraftInput) -> DraftOutput:
        suffix = sha256(f"{request.case_id}:{request.body}".encode()).hexdigest()[:10].upper()
        return DraftOutput(
            draft_id=f"{prefix}-{suffix}", case_id=request.case_id, body=request.body
        )

    @staticmethod
    def _copy_or_raise(
        values: Mapping[str, ModelT], key: str, label: str
    ) -> ModelT:
        value = values.get(key)
        if value is None:
            raise ProviderRecordNotFound(label)
        return value.model_copy(deep=True)
