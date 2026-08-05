from app.persistence.actions._base import (
    _connection_is_eligible as _connection_is_eligible,
)
from app.persistence.actions.execution import ActionExecutionRepository
from app.persistence.actions.materialization import ActionMaterializationRepository
from app.persistence.actions.queries import ActionQueryRepository
from app.persistence.actions.recovery import ActionRecoveryRepository


class ActionRepository(
    ActionMaterializationRepository,
    ActionQueryRepository,
    ActionExecutionRepository,
    ActionRecoveryRepository,
):
    """Facade preserving the public action persistence contract."""
