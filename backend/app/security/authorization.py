from app.domain.identity import ActorContext, Permission


class PermissionDenied(PermissionError):
    pass


def require_permission(actor: ActorContext, permission: Permission) -> None:
    if not actor.can(permission):
        raise PermissionDenied(f"Permission {permission.value} is required.")
