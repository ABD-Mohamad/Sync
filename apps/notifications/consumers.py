# apps/notifications/consumers.py
#
# UPDATED: Supports two session types on the same WebSocket endpoint:
#   1. User session       → group: notifications_user_{user_id}
#      Authenticated via JWT → scope['user'] set by JWTAuthMiddleware
#   2. Employee session   → group: notifications_employee_{employee_id}
#      Authenticated via Employee JWT → scope['employee'] set by JWTAuthMiddleware
#      (requires middleware update — see middleware.py)
#
# The consumer checks scope['user'] first (web users: DH, IT Manager).
# If user is anonymous it then checks scope['employee'] (Employee portal).
# This matches the dual-auth architecture of Django's backend.

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models  import AnonymousUser


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Unified WebSocket consumer for real-time notifications.

    Routing:
        User      → group: notifications_user_{user_id}
        Employee  → group: notifications_employee_{employee_id}

    Signals push to these groups via channel_layer.group_send().
    """

    async def connect(self):
        user     = self.scope.get('user')
        employee = self.scope.get('employee')   # set by updated JWTAuthMiddleware

        # ── Authenticated User (DH / IT Manager) ─────────────────────────────
        if user and not isinstance(user, AnonymousUser):
            self.session_type  = 'user'
            self.session_id    = user.id
            self.group_name    = f'notifications_user_{user.id}'

        # ── Authenticated Employee ────────────────────────────────────────────
        elif employee and getattr(employee, 'id', None):
            self.session_type  = 'employee'
            self.session_id    = employee.id
            self.group_name    = f'notifications_employee_{employee.id}'

        # ── Reject unauthenticated ────────────────────────────────────────────
        else:
            await self.close(code=4001)
            return

        # Join personal notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Welcome message so Angular knows the connection is live
        await self.send(text_data=json.dumps({
            'type'        : 'connection_established',
            'session_type': self.session_type,
            'message'     : 'Connected to notifications.',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        """
        Clients send a ping to keep the connection alive.
        We respond with a pong.

        Employees can also send their FCM token to be saved on the server:
            { "type": "register_fcm_token", "token": "<token>" }
        """
        try:
            data = json.loads(text_data)

            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

            elif data.get('type') == 'register_fcm_token':
                token = data.get('token', '').strip()
                if token:
                    await self._save_fcm_token(token)
                    await self.send(text_data=json.dumps({
                        'type'   : 'fcm_token_registered',
                        'message': 'FCM token saved.',
                    }))

        except json.JSONDecodeError:
            pass

    async def send_notification(self, event):
        """
        Handler called by channel_layer.group_send().
        Forwards the notification payload to the WebSocket client.
        Both User and Employee groups use the same handler name.
        """
        await self.send(text_data=json.dumps(event['data']))

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _save_fcm_token(self, token: str):
        """
        Persists the FCM token for the authenticated User or Employee.
        Called when client sends a 'register_fcm_token' message.
        """
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _update_token():
            if self.session_type == 'user':
                from apps.accounts.models import User
                User.objects.filter(id=self.session_id).update(fcm_token=token)
            elif self.session_type == 'employee':
                from apps.accounts.models import Employee
                Employee.objects.filter(id=self.session_id).update(fcm_token=token)

        await _update_token()