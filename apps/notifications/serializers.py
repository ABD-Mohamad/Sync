# apps/notifications/serializers.py
from rest_framework import serializers
from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    recipient = serializers.StringRelatedField(read_only=True)
    actor     = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Notification
        fields = [
            'id', 'recipient', 'actor', 'verb',
            'target_id', 'target_type', 'is_read', 'created_at',
        ]
        read_only_fields = [
            'id', 'recipient', 'actor', 'verb',
            'target_id', 'target_type', 'created_at',
        ]