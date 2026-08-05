from app.tools.contracts import SideEffectState


class ToolExecutionError(RuntimeError):
    def __init__(self, message: str, *, code: str, side_effect_state: SideEffectState) -> None:
        super().__init__(message)
        self.code = code
        self.side_effect_state = side_effect_state


class ProviderRejected(ToolExecutionError):
    def __init__(self, message: str = "Provider rejected the request.") -> None:
        super().__init__(
            message,
            code="provider_rejected",
            side_effect_state=SideEffectState.NONE,
        )


class ProviderTimeout(ToolExecutionError):
    def __init__(self, message: str = "Provider timed out after accepting the request.") -> None:
        super().__init__(
            message,
            code="provider_timeout_after_acceptance",
            side_effect_state=SideEffectState.POSSIBLE,
        )


class ProviderPreSendTimeout(ToolExecutionError):
    def __init__(self, message: str = "Provider connection timed out before request send.") -> None:
        super().__init__(
            message,
            code="provider_timeout_before_send",
            side_effect_state=SideEffectState.NOT_ATTEMPTED,
        )


class ProviderRecordNotFound(ToolExecutionError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            f"{resource} was not found.",
            code="provider_record_not_found",
            side_effect_state=SideEffectState.NONE,
        )


class BlindRetryBlocked(ToolExecutionError):
    def __init__(self) -> None:
        super().__init__(
            "A previous attempt may have changed external state. Reconcile before retrying.",
            code="blind_retry_blocked",
            side_effect_state=SideEffectState.POSSIBLE,
        )


class ApprovedActionRequired(PermissionError):
    pass
