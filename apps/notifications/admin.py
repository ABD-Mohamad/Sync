# apps/notifications/admin.py
from django.contrib             import admin
from apps.notifications.models  import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display   = ['recipient', 'actor', 'verb', 'target_type',
                      'target_id', 'is_read', 'created_at']
    list_filter    = ['is_read', 'target_type']
    search_fields  = ['recipient__email', 'verb']
    readonly_fields = ['recipient', 'actor', 'verb', 'target_id',
                       'target_type', 'created_at']