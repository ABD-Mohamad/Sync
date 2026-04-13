# apps/tasks/signals.py
#
# Hybrid Notification Router — Django Signals
#
# CHANNEL DECISION TABLE:
# ┌──────────────────────────────────────────────────────┬─────────────┬───────────┐
# │ Event                                                │ Recipient   │ Channel   │
# ├──────────────────────────────────────────────────────┼─────────────┼───────────┤
# │ MainTask created / updated — HIGH or URGENT priority │ Dept Head   │ FCM 🔥    │
# │ MainTask created / updated — LOW or MEDIUM priority  │ Dept Head   │ WebSocket │
# │ Request submitted — EXEMPTION type                   │ Dept Head   │ FCM 🔥    │
# │ Request submitted — EXTENSION type                   │ Dept Head   │ WebSocket │
# │ Request status → APPROVED or REJECTED                │ Employee    │ FCM 🔥    │
# │ SubTask assigned to Employee                         │ Employee    │ FCM 🔥    │
# │ SubTask status → AWAITING_REVIEW or COMPLETED        │ Manager     │ WebSocket │
# └──────────────────────────────────────────────────────┴─────────────┴───────────┘
#
# Notes:
#   • Department Head is a User (accounts.User) with role = 'department_head'.
#     Their department is resolved via MainTask.department or Request.subtask.main_task.department.
#   • Employee is accounts.Employee — has NO User account.
#     They receive FCM notifications via Employee.fcm_token.
#   • Existing `send_notification()` utility (apps.notifications.utils) handles
#     DB save + WebSocket push for User recipients.
#   • `send_fcm_to_user()` and `send_fcm_to_employee()` handle Firebase push.

import logging
from django.db.models.signals import post_save
from django.dispatch          import receiver

from apps.tasks.models import MainTask, SubTask, Request

logger = logging.getLogger(__name__)


# ── Helper: resolve Department Head for a given department FK ─────────────────

def _get_dept_head(department):
    """
    Returns the User with role=DEPARTMENT_HEAD assigned to `department`.
    Returns None if not found or if department is None.
    """
    if department is None:
        return None
    try:
        from apps.accounts.models import User, Role
        return (
            User.objects
            .select_related('role')
            .filter(department=department, role__name=Role.DEPARTMENT_HEAD)
            .first()
        )
    except Exception as exc:
        logger.warning('[Signals] _get_dept_head error: %s', exc)
        return None


# ── Helper: send WebSocket notification to a User ────────────────────────────

def _ws_notify_user(recipient, actor, verb, target_id, target_type):
    """Wrapper around the existing WebSocket notification utility."""
    try:
        from apps.notifications.utils import send_notification
        send_notification(
            recipient   = recipient,
            actor       = actor,
            verb        = verb,
            target_id   = target_id,
            target_type = target_type,
        )
    except Exception as exc:
        logger.error('[Signals] WebSocket notification failed: %s', exc)


# ── Helper: send FCM to a User ────────────────────────────────────────────────

def _fcm_notify_user(user, title, body, data=None):
    try:
        from apps.notifications.fcm_utils import send_fcm_to_user
        send_fcm_to_user(user, title=title, body=body, data=data or {})
    except Exception as exc:
        logger.error('[Signals] FCM (User) failed: %s', exc)


# ── Helper: send FCM to an Employee ──────────────────────────────────────────

def _fcm_notify_employee(employee, title, body, data=None):
    try:
        from apps.notifications.fcm_utils import send_fcm_to_employee
        send_fcm_to_employee(employee, title=title, body=body, data=data or {})
    except Exception as exc:
        logger.error('[Signals] FCM (Employee) failed: %s', exc)


# ── Helper: send WebSocket notification to an Employee ───────────────────────

def _ws_notify_employee(employee_id, verb, target_id, target_type, extra_data=None):
    """
    Pushes a WebSocket event to the employee's personal group:
        notifications_employee_{employee_id}
    This requires the NotificationConsumer to also support employee groups
    (see updated consumers.py).
    """
    try:
        from asgiref.sync    import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        group_name    = f'notifications_employee_{employee_id}'

        payload = {
            'type'       : 'send_notification',
            'data': {
                'verb'        : verb,
                'target_id'   : target_id,
                'target_type' : target_type,
                'actor'       : 'System',
                'is_read'     : False,
                **(extra_data or {}),
            },
        }
        async_to_sync(channel_layer.group_send)(group_name, payload)
    except Exception as exc:
        logger.error('[Signals] WS (Employee) failed: %s', exc)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL: MainTask
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=MainTask)
def main_task_notifications(sender, instance, created, update_fields=None, **kwargs):
    """
    Decision logic:
      • Priority HIGH / URGENT  → FCM to Department Head
      • Priority LOW  / MEDIUM  → WebSocket to Department Head

    Guard: update_fields protects against spurious re-fires on unrelated saves.
    """
    updated = set(update_fields) if update_fields else None

    # Only fire on explicit relevant saves (or on INSERT / no update_fields guard)
    if not created and updated and not (
        updated & {'priority', 'status', 'assigned_to', 'department', 'title'}
    ):
        return

    # Resolve Department Head recipient
    dept_head = (
        _get_dept_head(instance.department)
        or instance.assigned_to  # fallback: explicitly assigned DH
    )

    if not dept_head:
        return   # No DH to notify

    event_word = 'created' if created else 'updated'
    verb       = f'MainTask "{instance.title}" has been {event_word}.'
    link       = f'/main-tasks/{instance.id}'
    data       = {
        'target_type' : 'MainTask',
        'target_id'   : str(instance.id),
        'link'        : link,
        'priority'    : instance.priority,
    }

    high_priority = instance.priority in (
        MainTask.Priority.HIGH,
        MainTask.Priority.URGENT,
    )

    if high_priority:
        # 🔥 FCM — critical / urgent — browser push notification
        _fcm_notify_user(
            user  = dept_head,
            title = f'⚠️ {instance.get_priority_display()} Task {event_word.capitalize()}: {instance.title}',
            body  = f'Priority: {instance.get_priority_display()} | Status: {instance.get_status_display()}',
            data  = data,
        )
        logger.info(
            '[Signals] FCM sent to DH %s for %s priority MainTask %s',
            dept_head.id, instance.priority, instance.id,
        )
    else:
        # 📡 WebSocket — routine — in-app notification
        _ws_notify_user(
            recipient   = dept_head,
            actor       = instance.created_by,
            verb        = verb,
            target_id   = instance.id,
            target_type = 'MainTask',
        )
        logger.info(
            '[Signals] WS sent to DH %s for %s priority MainTask %s',
            dept_head.id, instance.priority, instance.id,
        )

    # ── Self-assignment confirmation to Manager ────────────────────────────
    if instance.assigned_to and instance.status == MainTask.Status.ASSIGNED:
        if updated is None or 'assigned_to' in updated or 'status' in updated:
            _ws_notify_user(
                recipient   = instance.assigned_to,
                actor       = instance.created_by,
                verb        = f'You have been assigned MainTask "{instance.title}".',
                target_id   = instance.id,
                target_type = 'MainTask',
            )


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL: SubTask
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=SubTask)
def subtask_notifications(sender, instance, created, update_fields=None, **kwargs):
    """
    Decision logic:
      • SubTask newly assigned to Employee
          → FCM to Employee (immediate push — this is the most important subtask event)
      • SubTask status → AWAITING_REVIEW or COMPLETED
          → WebSocket to Manager (created_by on main_task)
    """
    updated = set(update_fields) if update_fields else None

    # ── NEW ASSIGNMENT: SubTask created and assigned to an Employee ───────────
    if created and instance.assigned_to:
        employee = instance.assigned_to  # accounts.Employee instance

        # 🔥 FCM to Employee — immediate browser push
        _fcm_notify_employee(
            employee = employee,
            title    = '📋 New Task Assigned',
            body     = f'"{instance.title}" has been assigned to you. Due: {instance.due_date or "not set"}',
            data     = {
                'target_type' : 'SubTask',
                'target_id'   : str(instance.id),
                'main_task_id': str(instance.main_task_id),
                'link'        : f'/employee/my-tasks?taskId={instance.main_task_id}',
            },
        )
        logger.info(
            '[Signals] FCM sent to Employee %s for new SubTask %s',
            employee.id, instance.id,
        )

        # Also send WebSocket to the same employee (for in-app banner)
        _ws_notify_employee(
            employee_id = employee.id,
            verb        = f'New subtask "{instance.title}" assigned to you.',
            target_id   = instance.id,
            target_type = 'SubTask',
        )

        # Notify Department Head (User) via WebSocket
        dh = instance.main_task.assigned_to   # User (Dept Head) or None
        if dh:
            _ws_notify_user(
                recipient   = dh,
                actor       = instance.created_by,
                verb        = (
                    f'New subtask "{instance.title}" assigned to '
                    f'{employee.full_name}.'
                ),
                target_id   = instance.id,
                target_type = 'SubTask',
            )
        return

    # ── STATUS UPDATE ─────────────────────────────────────────────────────────
    if not created and (updated is None or 'status' in updated):
        status_labels = {
            SubTask.Status.AWAITING_REVIEW : 'is awaiting your review',
            SubTask.Status.COMPLETED       : 'has been completed',
        }
        label = status_labels.get(instance.status)

        if label:
            manager = instance.main_task.created_by   # User (Manager / IT)
            if manager:
                _ws_notify_user(
                    recipient   = manager,
                    actor       = None,    # Employee has no User FK
                    verb        = f'SubTask "{instance.title}" {label}.',
                    target_id   = instance.id,
                    target_type = 'SubTask',
                )


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL: Request
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=Request)
def request_notifications(sender, instance, created, update_fields=None, **kwargs):
    """
    Decision logic:
      • New EXEMPTION request submitted
          → FCM to Department Head (urgent — exemption removes employee from subtask)
      • New EXTENSION request submitted
          → WebSocket to Department Head (routine — just needs review)
      • Request status changed to APPROVED or REJECTED
          → FCM to Employee (result of their request)
    """
    updated = set(update_fields) if update_fields else None

    # Resolve Department Head for this request
    dept_head = _get_dept_head(instance.subtask.main_task.department)
    if not dept_head:
        dept_head = instance.subtask.main_task.assigned_to   # fallback

    # ── NEW REQUEST SUBMITTED ─────────────────────────────────────────────────
    if created:
        request_type_label = instance.get_request_type_display()
        employee_name      = instance.employee.full_name
        link               = f'/requests/{instance.id}'
        data               = {
            'target_type'  : 'Request',
            'target_id'    : str(instance.id),
            'request_type' : instance.request_type,
            'link'         : link,
        }

        if instance.request_type == Request.RequestType.EXEMPTION:
            # 🔥 FCM — Exemption is critical (removes employee from task)
            if dept_head:
                _fcm_notify_user(
                    user  = dept_head,
                    title = f'🚨 Exemption Request: {employee_name}',
                    body  = (
                        f'{employee_name} requested an exemption from '
                        f'"{instance.subtask.title}". Immediate review required.'
                    ),
                    data  = data,
                )
                logger.info(
                    '[Signals] FCM sent to DH %s for EXEMPTION request %s',
                    dept_head.id, instance.id,
                )

        elif instance.request_type == Request.RequestType.EXTENSION:
            # 📡 WebSocket — Extension is routine
            if dept_head:
                _ws_notify_user(
                    recipient   = dept_head,
                    actor       = None,
                    verb        = (
                        f'{employee_name} submitted an extension request '
                        f'for "{instance.subtask.title}" '
                        f'(+{instance.extension_days or "?"} days).'
                    ),
                    target_id   = instance.id,
                    target_type = 'Request',
                )
                logger.info(
                    '[Signals] WS sent to DH %s for EXTENSION request %s',
                    dept_head.id, instance.id,
                )
        return

    # ── REQUEST STATUS CHANGED (APPROVED / REJECTED) ──────────────────────────
    if not created and (updated is None or 'status' in updated):
        if instance.status in (Request.Status.APPROVED, Request.Status.REJECTED):
            employee = instance.employee   # accounts.Employee

            status_label = 'APPROVED ✅' if instance.status == Request.Status.APPROVED else 'REJECTED ❌'
            request_type = instance.get_request_type_display()

            # 🔥 FCM to Employee — this is the most important event for them
            _fcm_notify_employee(
                employee = employee,
                title    = f'Request {status_label}',
                body     = (
                    f'Your {request_type} for "{instance.subtask.title}" '
                    f'has been {instance.status}.'
                    + (
                        f' Reason: {instance.rejection_reason}'
                        if instance.status == Request.Status.REJECTED
                        and instance.rejection_reason
                        else ''
                    )
                ),
                data     = {
                    'target_type' : 'Request',
                    'target_id'   : str(instance.id),
                    'status'      : instance.status,
                    'link'        : '/employee/requests',
                },
            )

            # Also notify employee via WebSocket (in-app banner)
            _ws_notify_employee(
                employee_id = employee.id,
                verb        = (
                    f'Your {request_type} has been {instance.status}.'
                ),
                target_id   = instance.id,
                target_type = 'Request',
                extra_data  = {'status': instance.status},
            )

            logger.info(
                '[Signals] FCM + WS sent to Employee %s — Request %s %s',
                employee.id, instance.id, instance.status,
            )