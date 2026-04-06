# apps/accounts/audit.py
import functools
import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger('sync.audit')


class AuditLog(models.Model):
    """
    Stores a record of every significant action taken in the system.
    This is the AOP 'cross-cutting concern' — applied across all views
    without cluttering business logic.
    """
    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        LOGIN  = 'login',  'Login'
        LOGOUT = 'logout', 'Logout'

    actor        = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    action       = models.CharField(max_length=10, choices=Action.choices)
    resource     = models.CharField(max_length=100)  # e.g. "User", "Employee"
    resource_id  = models.CharField(max_length=50, blank=True)
    detail       = models.TextField(blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    timestamp    = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']

    def __str__(self):
        actor = self.actor.email if self.actor else 'Anonymous'
        ts    = self.timestamp.strftime('%Y-%m-%d %H:%M')
        return f'[{self.action.upper()}] {self.resource} by {actor} at {ts}'


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def audit_action(action, resource):
    """
    AOP Decorator — wraps any ViewSet method to automatically log the action.

    Usage:
        @audit_action(action='create', resource='User')
        def create(self, request, *args, **kwargs):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            response = func(self, request, *args, **kwargs)

            # Only log on success (2xx responses)
            if response.status_code < 300:
                actor = request.user if request.user.is_authenticated else None
                
                resource_id = ''
                if hasattr(response, 'data') and isinstance(response.data, dict):
                    resource_id = str(response.data.get('id', ''))
                if not resource_id and 'pk' in kwargs:
                    resource_id = str(kwargs.get('pk'))

                AuditLog.objects.create(
                    actor=actor,
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    ip_address=get_client_ip(request),
                )

                logger.info(
                    f'AUDIT | {action.upper()} {resource} id={resource_id} '
                    f'by={actor} ip={get_client_ip(request)}'
                )

            return response
        return wrapper
    return decorator