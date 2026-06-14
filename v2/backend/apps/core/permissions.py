from rest_framework.permissions import SAFE_METHODS, BasePermission

_WRITE_ROLES = {"manager", "accountant"}


class IsManagerOrAdmin(BasePermission):
    """Require manager or accountant role (or superuser) for all methods."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or getattr(request.user, "role", None) in _WRITE_ROLES)
        )


class ReadOrManagerWrite(BasePermission):
    """Safe methods for any authenticated user; mutations for managers/accountants only."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or getattr(request.user, "role", None) in _WRITE_ROLES
