# apps/notifications/views.py
from rest_framework                 import mixins, viewsets, status
from rest_framework.decorators      import action
from rest_framework.permissions     import IsAuthenticated
from rest_framework.response        import Response
from drf_spectacular.utils          import extend_schema

from apps.notifications.models      import Notification
from apps.notifications.serializers import NotificationSerializer
from apps.accounts.audit            import audit_action


class NotificationViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/notifications/           — list my notifications
    GET  /api/notifications/unread/    — list only unread
    POST /api/notifications/{id}/read/ — mark one as read
    POST /api/notifications/read-all/  — mark all as read
    """
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related('actor')

    @extend_schema(
        responses={200: NotificationSerializer(many=True)},
        summary='List my notifications',
        tags=['Notifications'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={200: NotificationSerializer(many=True)},
        summary='List my unread notifications',
        tags=['Notifications'],
    )
    @action(detail=False, methods=['get'], url_path='unread')
    def unread(self, request):
        qs = self.get_queryset().filter(is_read=False)
        serializer = NotificationSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: NotificationSerializer},
        summary='Mark a notification as read',
        tags=['Notifications'],
    )
    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary='Mark all notifications as read',
        tags=['Notifications'],
    )
    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'})

    @extend_schema(
        summary='Get unread notification count',
        tags=['Notifications'],
    )
    @action(detail=False, methods=['get'], url_path='count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})