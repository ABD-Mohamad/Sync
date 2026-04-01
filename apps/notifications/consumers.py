# apps/notifications/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models  import AnonymousUser


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.

    Each authenticated user gets their own group:
        notifications_user_{user_id}

    The consumer:
    1. Connects — joins the user's personal group
    2. Receives push from channel layer — forwards to WebSocket
    3. Disconnects — leaves the group
    """

    async def connect(self):
        user = self.scope.get('user')

        # Reject anonymous connections
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return

        self.user_id    = user.id
        self.group_name = f'notifications_user_{self.user_id}'

        # Join personal notification group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

        # Send a welcome message so the client knows the connection is live
        await self.send(text_data=json.dumps({
            'type'   : 'connection_established',
            'message': 'Connected to notifications.',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        """
        Clients can send a ping to keep the connection alive.
        We respond with a pong.
        """
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            pass

    async def send_notification(self, event):
        """
        Handler called by channel_layer.group_send().
        Forwards the notification payload to the WebSocket client.
        """
        await self.send(text_data=json.dumps(event['data']))