# apps/tasks/signals.py
from django.db.models.signals import post_save
from django.dispatch          import receiver
from apps.tasks.models        import MainTask, SubTask


# ✅ Use update_fields to guard — or track dirty fields
@receiver(post_save, sender=MainTask)
def main_task_notifications(sender, instance, created, update_fields=None, **kwargs):
    from apps.notifications.utils import send_notification

    if created:
        send_notification(recipient=instance.created_by, ...)
        return

    # Only notify assignment if status field was explicitly updated to ASSIGNED
    if (update_fields and 'status' in update_fields
            and instance.assigned_to
            and instance.status == MainTask.Status.ASSIGNED):
        send_notification(recipient=instance.assigned_to, ...)

    # Only notify status change if status field changed
    if update_fields and 'status' in update_fields and instance.assigned_to:
        status_labels = { ... }
        label = status_labels.get(instance.status)
        if label:
            send_notification(recipient=instance.created_by, ...)

            
@receiver(post_save, sender=SubTask)
def subtask_notifications(sender, instance, created, **kwargs):
    from apps.notifications.utils import send_notification

    # SubTask assigned_to is an Employee — they get mobile push, not WebSocket.
    # Notify the main task's creator (a web User) about status changes.

    if not created and instance.main_task.created_by:
        status_labels = {
            SubTask.Status.AWAITING_REVIEW: 'is awaiting your review',
            SubTask.Status.COMPLETED      : 'has been completed',
        }
        label = status_labels.get(instance.status)
        if label:
            send_notification(
                recipient   = instance.main_task.created_by,   # ← always a User ✅
                actor       = None,                             # Employee has no User
                verb        = f'SubTask "{instance.title}" {label}',
                target_id   = instance.id,
                target_type = 'SubTask',
            )