__all__ = ['IsITOrAdmin']
from rest_framework.permissions import BasePermission


class IsITOrAdmin(BasePermission):
    """
    AOP Permission — applied as a cross-cutting concern on any view
    that requires IT role or superuser (admin) access.

    Allows access only to:
    - Django superusers (admin)
    - Users whose role is 'it'
    """
    message = 'Access denied. IT role or Admin privileges required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.role is not None and
            request.user.role.name == 'it'
        )