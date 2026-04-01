# apps/accounts/permissions.py
from rest_framework.permissions import BasePermission
from apps.accounts.models       import Role


class IsITOrAdmin(BasePermission):
    """IT role or superuser — existing permission."""
    message = 'Access denied. IT role or Admin privileges required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.role is not None and
            request.user.role.name == Role.IT
        )


class IsManager(BasePermission):
    """
    Grants access if the user is a superuser OR has the IT role.
    In this system the IT role acts as the manager — they create
    and manage tasks, users, and departments.
    """
    message = 'Access denied. Manager privileges required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.role is not None and
            request.user.role.name == Role.IT
        )


class IsDepartmentHead(BasePermission):
    """
    Grants access if the user's role is department_head.
    """
    message = 'Access denied. Department Head role required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.role is not None and
            request.user.role.name == Role.DEPARTMENT_HEAD
        )

    def has_object_permission(self, request, view, obj):
        """Department Head can only act on tasks assigned to them."""
        return obj.assigned_to == request.user