# apps/notifications/notification_urls.py
#
# URL patterns for the notifications app.
#
# Include in your project-level urls.py:
#   from django.urls import path, include
#   ...
#   path('api/notifications/', include('apps.notifications.notification_urls')),

from django.urls import path
from apps.notifications.fcm_views import RegisterFCMTokenView

urlpatterns = [
    # PATCH /api/notifications/fcm-token/  → register browser FCM token
    # DELETE /api/notifications/fcm-token/ → clear on logout
    path('fcm-token/', RegisterFCMTokenView.as_view(), name='notifications-fcm-token'),
]