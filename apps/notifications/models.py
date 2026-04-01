# apps/notifications/models.py
from django.db   import models
from django.conf import settings


class Notification(models.Model):
    """
    Stores a notification for a specific user.

    recipient  — the User who receives the notification
    actor      — the User who triggered the action (nullable for system events)
    verb       — human-readable description e.g. 'created', 'assigned', 'status_updated'
    target_id  — the ID of the object the action was performed on (task ID, subtask ID, etc.)
    target_type — the type of target e.g. 'MainTask', 'SubTask'
    is_read    — whether the user has read the notification
    created_at — timestamp
    """
    recipient   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_notifications',
    )
    verb        = models.CharField(max_length=255)
    target_id   = models.PositiveIntegerField(null=True, blank=True)
    target_type = models.CharField(max_length=50, blank=True)
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering            = ['-created_at']

    def __str__(self):
        return f'[{self.recipient}] {self.verb}'