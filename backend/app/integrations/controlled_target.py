"""Synthetic business objects with observable changes, separate from request receipts."""

from copy import deepcopy
from decimal import Decimal

from app.domain.controlled_operations import OPERATIONS


class ControlledTarget:
    def __init__(self, objects: dict[str, dict[str, str]] | None = None) -> None:
        self.objects = deepcopy(objects or {})
        self.effects: dict[str, tuple[str, dict[str, str], dict[str, str]]] = {}

    def prepare(
        self,
        *,
        action_type: str,
        provider: str,
        target: str,
        parameters: dict[str, str],
        amount: Decimal | None,
        currency: str | None,
    ) -> dict[str, str]:
        spec = OPERATIONS[action_type]
        current = self.objects.get(target)
        if current is None or spec.provider != provider:
            raise ValueError("No matching synthetic target is configured")
        required = {"external_reference", "recipient", "reason_code", *spec.value_fields}
        required.update(
            {"access_scope", "preserve_owner"} if spec.scope else {"amount_minor", "currency"}
        )
        if set(parameters) != required or any(not value.strip() for value in parameters.values()):
            raise ValueError("Operation payload is incomplete or has unexpected fields")
        if (
            parameters["external_reference"] != target
            or current.get("owner") != parameters["recipient"]
        ):
            raise ValueError("Target or original owner does not match")
        if spec.scope:
            if parameters["access_scope"] != spec.scope or parameters["preserve_owner"] != "true":
                raise ValueError("Identity scope or ownership preservation mismatch")
            if amount is not None or currency is not None:
                raise ValueError("An identity change cannot carry a financial effect")
        else:
            minor = parameters["amount_minor"]
            if not minor.isascii() or not minor.isdigit() or len(minor) > 12:
                raise ValueError("Invalid amount")
            if amount != Decimal(minor) / 100 or currency != parameters["currency"]:
                raise ValueError("Monetary impact does not match the approved parameters")
            if spec.transfers_money and int(minor) <= 0:
                raise ValueError("A transfer must have a positive amount")
        changes = {key: parameters[key] for key in spec.value_fields}
        if action_type == "change_draft_currency":
            if current.get("invoice_state") != "draft":
                raise ValueError("Only a draft invoice may change currency")
            changes.update(currency=parameters["currency"], amount_minor=parameters["amount_minor"])
        elif action_type == "revoke_compromised_sessions":
            changes["active_sessions"] = "0"
        elif spec.transfers_money:
            balance = current.get("credited_minor", "0")
            if not balance.isdigit() or current.get("currency") != currency:
                raise ValueError("Target ledger amount/currency is invalid")
            changes["credited_minor"] = str(int(balance) + int(parameters["amount_minor"]))
        return changes

    def commit(
        self, operation_id: str, target: str, parameters: dict[str, str], changes: dict[str, str]
    ) -> None:
        if operation_id in self.effects:
            raise ValueError("An operation may affect the target only once")
        self.objects[target].update(changes)
        self.effects[operation_id] = (target, dict(parameters), dict(changes))

    def readback(self, operation_id: str) -> tuple[dict[str, str], bool]:
        target, parameters, changes = self.effects[operation_id]
        current = self.objects.get(target, {})
        matches = current.get("owner") == parameters["recipient"] and all(
            current.get(key) == value for key, value in changes.items()
        )
        # Parameters are read from the effect ledger. Changed business values come from the
        # current object, so a later invalidation cannot be hidden by the saved request.
        observed = dict(parameters)
        for key in changes.keys() & parameters.keys():
            observed[key] = current.get(key, "<missing>")
        return observed, matches
