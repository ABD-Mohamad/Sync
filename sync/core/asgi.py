# sync/core/asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.asgi                             import get_asgi_application
from channels.routing                             import ProtocolTypeRouter, URLRouter
from apps.notifications.middleware                import JWTAuthMiddleware
from apps.notifications.routing                   import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http'     : get_asgi_application(),
    'websocket': JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})