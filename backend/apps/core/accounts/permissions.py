from rest_framework.permissions import SAFE_METHODS, BasePermission


class _HasRole(BasePermission):
    roles = ()

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role in self.roles)


class IsAdmin(_HasRole):
    roles = ("admin",)


class IsStaffOrAdmin(_HasRole):
    roles = ("admin", "staff")


class IsCustomer(_HasRole):
    roles = ("customer",)


class ReadOnlyOrAdmin(BasePermission):
    """Catalog-style resources: staff and admin may read, only admin may write; customers get nothing."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return u.role in ("admin", "staff")
        return u.role == "admin"
