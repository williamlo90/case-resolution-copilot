from app.domain.actions import (
    ActionCommand,
    ActionExecutionBlocker,
    ActionPageRecord,
    ActionQueueItemRecord,
    ActionStatus,
)
from app.domain.identity import ActorContext
from app.security.authentication import DeterministicAuthProvider
from app.services.action_service import (
    ActionQueryService,
    available_action_commands,
)
from tests.builders import valid_action_bundle


def _item(
    *,
    status: ActionStatus = ActionStatus.READY,
    blocker: ActionExecutionBlocker | None = None,
    adapter_key: str = "deterministic_demo",
) -> ActionQueueItemRecord:
    bundle = valid_action_bundle(
        status=status,
        execution_blocker=blocker,
        adapter_key=adapter_key,
    )
    return ActionQueueItemRecord(
        bundle=bundle,
        effective_blocker=blocker,
        recovery_required=status in {ActionStatus.OUTCOME_UNKNOWN, ActionStatus.RECOVERY_REQUIRED},
    )


class _Store:
    def __init__(self, item: ActionQueueItemRecord) -> None:
        self.item = item
        self.reads = 0

    def get(self, **values: object) -> ActionQueueItemRecord:
        del values
        self.reads += 1
        return self.item

    def list(self, **values: object) -> ActionPageRecord:
        del values
        self.reads += 1
        return ActionPageRecord(items=[self.item], next_cursor=None, total=1)


def _actor(actor_id: str) -> ActorContext:
    return DeterministicAuthProvider().authenticate(actor_id)


def test_read_only_specialist_sees_permission_blocker_not_execute_command() -> None:
    store = _Store(_item())
    detail = ActionQueryService(store).get(
        actor=_actor("USR-0001"),
        action_id="AC-TEST",
    )

    assert detail.effective_blocker is ActionExecutionBlocker.PERMISSION
    assert (
        available_action_commands(
            actor=_actor("USR-0001"),
            item=detail,
        )
        == []
    )


def test_supervisor_sees_execute_only_for_a_ready_unblocked_action() -> None:
    detail = _item()

    assert available_action_commands(
        actor=_actor("USR-0002"),
        item=detail,
    ) == [ActionCommand.EXECUTE]


def test_safe_failure_and_unknown_outcome_never_share_retry_semantics() -> None:
    safe_failure = _item(status=ActionStatus.FAILED_SAFE)
    unknown = _item(status=ActionStatus.OUTCOME_UNKNOWN)

    assert available_action_commands(
        actor=_actor("USR-0002"),
        item=safe_failure,
    ) == [ActionCommand.RETRY_SAFE, ActionCommand.ESCALATE]
    unknown_commands = available_action_commands(
        actor=_actor("USR-0002"),
        item=unknown,
    )
    assert ActionCommand.RETRY_SAFE not in unknown_commands
    assert unknown_commands == [
        ActionCommand.RECONCILE,
        ActionCommand.RECORD_MANUAL_OUTCOME,
        ActionCommand.ESCALATE,
    ]


def test_unconfigured_target_hides_reconcile_but_keeps_manual_recovery() -> None:
    unknown = _item(
        status=ActionStatus.OUTCOME_UNKNOWN,
        adapter_key="unconfigured",
    )

    assert available_action_commands(
        actor=_actor("USR-0002"),
        item=unknown,
    ) == [
        ActionCommand.RECORD_MANUAL_OUTCOME,
        ActionCommand.ESCALATE,
    ]


def test_escalated_safe_failure_does_not_masquerade_as_unknown_outcome() -> None:
    recovery = _item(status=ActionStatus.RECOVERY_REQUIRED)

    assert (
        available_action_commands(
            actor=_actor("USR-0002"),
            item=recovery,
        )
        == []
    )
