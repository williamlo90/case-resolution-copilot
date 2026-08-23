class InboxNotFound(LookupError):
    pass


class InboxConflict(RuntimeError):
    pass


class InboxAuthorizationError(RuntimeError):
    pass


class InboxCredentialUnavailable(RuntimeError):
    pass


class InboxProviderUnavailable(RuntimeError):
    pass


class InboxSyncUnavailable(RuntimeError):
    pass


class InboxVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The inbox connection changed after version {expected_version}; "
            f"current version is {current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version
