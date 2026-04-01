# apps/notifications/utils.py
from asgiref.sync          import async_to_sync
from channels.layers       import get_channel_layer
from apps.notifications.models import Notification


def send_notification(recipient, actor, verb, target_id=None, target_type=''):
    """
    1. Saves the notification to the database
    2. Pushes it to the user's WebSocket group in real-time

    Called from signals — works in both sync and async contexts.
    """
    # Save to DB
    notification = Notification.objects.create(
        recipient   = recipient,
        actor       = actor,
        verb        = verb,
        target_id   = target_id,
        target_type = target_type,
    )

    # Push to WebSocket
    channel_layer = get_channel_layer()
    group_name    = f'notifications_user_{recipient.id}'

    payload = {
        'id'         : notification.id,
        'verb'       : notification.verb,
        'target_id'  : notification.target_id,
        'target_type': notification.target_type,
        'actor'      : str(actor) if actor else 'System',
        'is_read'    : False,
        'created_at' : notification.created_at.isoformat(),
    }

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'send_notification',  # maps to consumer.send_notification()
            'data': payload,
        },
    )

    return notification