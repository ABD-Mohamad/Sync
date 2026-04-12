# apps/tasks/signals.py
from django.db.models.signals import post_save
from django.dispatch          import receiver
from apps.tasks.models        import MainTask, SubTask


@receiver(post_save, sender=MainTask)
def main_task_notifications(sender, instance, created, update_fields=None, **kwargs):
    """
    Fires on every MainTask save.

    Guards:
    - 'created'      → only on first INSERT
    - 'update_fields' → only when status or assigned_to was explicitly saved,
      preventing spurious re-fires on unrelated field updates (Fix #12).

    All recipients are web Users (Manager / Department Head) — they have
    accounts in the auth system and a Notification FK to User is valid.
    """
    from apps.notifications.utils import send_notification

    # ── Task Created ──────────────────────────────────────────────────────────
    if created:
        send_notification(
            recipient   = instance.created_by,
            actor       = instance.created_by,
            verb        = f'You created task "{instance.title}"',
            target_id   = instance.id,
            target_type = 'MainTask',
        )
        return

    # From here on we only care about explicit field updates (Fix #12).
    # Views that call task.save(update_fields=['status', 'updated_at'])
    # or serializer.save(...) will trigger this; bulk operations that
    # don't pass update_fields will also trigger (update_fields is None),
    # which is a safe fallback.
    updated = set(update_fields) if update_fields else None

    # ── Task Assigned (status changed to ASSIGNED) ────────────────────────────
    # Only fire when status was explicitly saved and the new value is ASSIGNED.
    if (
        instance.assigned_to
        and instance.status == MainTask.Status.ASSIGNED
        and (updated is None or 'status' in updated)
    ):
        send_notification(
            recipient   = instance.assigned_to,       # User (Department Head) ✓
            actor       = instance.created_by,
            verb        = f'You have been assigned task "{instance.title}"',
            target_id   = instance.id,
            target_type = 'MainTask',
        )

    # ── Status change notifications (IN_PROGRESS / COMPLETED) ─────────────────
    if updated is None or 'status' in updated:
        status_labels = {
            MainTask.Status.IN_PROGRESS: 'is now In Progress',
            MainTask.Status.COMPLETED  : 'has been Completed',
        }
        label = status_labels.get(instance.status)
        if label and instance.assigned_to:
            send_notification(
                recipient   = instance.created_by,    # User (Manager) ✓
                actor       = instance.assigned_to,   # User (Department Head) ✓
                verb        = f'Task "{instance.title}" {label}',
                target_id   = instance.id,
                target_type = 'MainTask',
            )


@receiver(post_save, sender=SubTask)
def subtask_notifications(sender, instance, created, update_fields=None, **kwargs):
    """
    Fires on every SubTask save.

    FIX #8: SubTask.assigned_to is now an Employee (Fix #1 in models.py).
    Notification.recipient is FK to AUTH_USER_MODEL (User).
    Sending an Employee instance as recipient would crash with an
    IntegrityError / ValueError.

    Rule: only notify web Users (Manager / Department Head) here.
    Employees receive notifications via mobile push (separate channel,
    not yet implemented).

    FIX #12: update_fields guard prevents spurious re-fires.
    """
    from apps.notifications.utils import send_notification

    updated = set(update_fields) if update_fields else None

    # ── SubTask Created and assigned ──────────────────────────────────────────
    # Employee (instance.assigned_to) would get a mobile push — skip here.
    # Notify the Department Head that a subtask was created under their task.
    if created and instance.assigned_to:
        dh = instance.main_task.assigned_to   # User (Department Head) ✓
        if dh:
            send_notification(
                recipient   = dh,
                actor       = instance.created_by,   # User (DH who created it) ✓
                verb        = (
                    f'New subtask "{instance.title}" assigned to '
                    f'{instance.assigned_to.full_name}'
                ),
                target_id   = instance.id,
                target_type = 'SubTask',
            )
        return

    # ── SubTask Status Updated ────────────────────────────────────────────────
    # Notify the Manager (main_task.created_by) when employee marks
    # subtask as AWAITING_REVIEW or COMPLETED.
    if not created and (updated is None or 'status' in updated):
        status_labels = {
            SubTask.Status.AWAITING_REVIEW: 'is awaiting your review',
            SubTask.Status.COMPLETED      : 'has been completed',
        }
        label = status_labels.get(instance.status)
        if label:
            manager = instance.main_task.created_by   # User (Manager) ✓
            if manager:
                send_notification(
                    recipient   = manager,
                    actor       = None,   # Employee has no User — pass None
                    verb        = f'SubTask "{instance.title}" {label}',
                    target_id   = instance.id,
                    target_type = 'SubTask',
                )