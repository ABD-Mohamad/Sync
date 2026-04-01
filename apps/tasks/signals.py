# apps/tasks/signals.py
from django.db.models.signals import post_save
from django.dispatch          import receiver
from apps.tasks.models        import MainTask, SubTask


@receiver(post_save, sender=MainTask)
def main_task_notifications(sender, instance, created, **kwargs):
    from apps.notifications.utils import send_notification

    # ── Task Created ──────────────────────────────────────────
    if created:
        # Notify the creator (confirmation)
        send_notification(
            recipient   = instance.created_by,
            actor       = instance.created_by,
            verb        = f'You created task "{instance.title}"',
            target_id   = instance.id,
            target_type = 'MainTask',
        )
        return

    # ── Task Assigned ─────────────────────────────────────────
    if instance.assigned_to and instance.status == MainTask.Status.ASSIGNED:
        send_notification(
            recipient   = instance.assigned_to,
            actor       = instance.created_by,
            verb        = f'You have been assigned task "{instance.title}"',
            target_id   = instance.id,
            target_type = 'MainTask',
        )

    # ── Status Updated ────────────────────────────────────────
    if not created and instance.assigned_to:
        status_labels = {
            MainTask.Status.IN_PROGRESS: 'is now In Progress',
            MainTask.Status.COMPLETED  : 'has been Completed',
        }
        label = status_labels.get(instance.status)
        if label:
            send_notification(
                recipient   = instance.created_by,
                actor       = instance.assigned_to,
                verb        = f'Task "{instance.title}" {label}',
                target_id   = instance.id,
                target_type = 'MainTask',
            )


@receiver(post_save, sender=SubTask)
def subtask_notifications(sender, instance, created, **kwargs):
    from apps.notifications.utils import send_notification

    # ── SubTask Created ───────────────────────────────────────
    if created and instance.assigned_to:
        send_notification(
            recipient   = instance.assigned_to,
            actor       = instance.created_by,
            verb        = f'You have been assigned subtask "{instance.title}"',
            target_id   = instance.id,
            target_type = 'SubTask',
        )
        return

    # ── SubTask Status Updated ────────────────────────────────
    if not created and instance.assigned_to:
        status_labels = {
            SubTask.Status.AWAITING_REVIEW: 'is awaiting your review',
            SubTask.Status.COMPLETED      : 'has been completed',
        }
        label = status_labels.get(instance.status)
        if label:
            # Notify the main task's creator (the manager)
            send_notification(
                recipient   = instance.main_task.created_by,
                actor       = instance.assigned_to,
                verb        = f'SubTask "{instance.title}" {label}',
                target_id   = instance.id,
                target_type = 'SubTask',
            )