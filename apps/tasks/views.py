# apps/tasks/views.py
from rest_framework             import status, viewsets
from rest_framework.decorators  import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response    import Response
from rest_framework.parsers     import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils      import extend_schema

from apps.tasks.models         import MainTask, TaskAttachment
from apps.tasks.serializers    import MainTaskSerializer, TaskAttachmentSerializer
from apps.tasks.state_machine  import validate_transition
from apps.accounts.permissions import IsManager, IsDepartmentHead
from apps.accounts.audit       import audit_action


class MainTaskViewSet(viewsets.ModelViewSet):
    # Requirements 3 — select_related + prefetch_related
    queryset = MainTask.objects.select_related(
        'created_by',
        'assigned_to',
        'assigned_to__department',
        'department',
    ).prefetch_related(
        'attachments',               # avoids N+1 on file listing
        'attachments__uploaded_by',
    ).all()

    serializer_class = MainTaskSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['status', 'priority']

    # Accept multipart for file uploads
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'my_tasks']:
            return [IsAuthenticated()]
        if self.action == 'update_status':
            return [IsAuthenticated()]   # object-level check inside the action
        return [IsAuthenticated(), IsManager()]

    # ── CRUD ──────────────────────────────────────────────────

    @extend_schema(
        responses={201: MainTaskSerializer},
        summary='Create a main task',
        tags=['Main Tasks'],
    )
    @audit_action(action='create', resource='MainTask')
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Requirement 4 — status auto-set to UNASSIGNED on creation
        serializer.save(
            created_by=self.request.user,
            status=MainTask.Status.UNASSIGNED,
        )

    @extend_schema(
        responses={200: MainTaskSerializer(many=True)},
        summary='List all main tasks',
        tags=['Main Tasks'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={200: MainTaskSerializer},
        summary='Get a main task',
        tags=['Main Tasks'],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=MainTaskSerializer,
        responses={200: MainTaskSerializer},
        summary='Update a main task',
        tags=['Main Tasks'],
    )
    @audit_action(action='update', resource='MainTask')
    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a main task',
        tags=['Main Tasks'],
    )
    @audit_action(action='delete', resource='MainTask')
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    # ── Assign ────────────────────────────────────────────────

    @extend_schema(
        request=MainTaskSerializer,
        responses={200: MainTaskSerializer},
        summary='Assign task to Department Head — auto-sets department + status',
        tags=['Main Tasks'],
    )
    @audit_action(action='update', resource='MainTask')
    @action(
        detail=True, methods=['patch'], url_path='assign',
        permission_classes=[IsAuthenticated, IsManager],
    )
    def assign(self, request, pk=None):
        task       = self.get_object()
        serializer = MainTaskSerializer(
            task,
            data={'assigned_to': request.data.get('assigned_to')},
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        department_head = serializer.validated_data.get('assigned_to')
        if not department_head:
            return Response(
                {'detail': 'assigned_to is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Requirement 4 — auto-set department + status → ASSIGNED
        serializer.save(
            status=MainTask.Status.ASSIGNED,
            department=department_head.department,
        )

        task.refresh_from_db()
        return Response(
            MainTaskSerializer(task, context={'request': request}).data
        )

    # ── Status Update with State Machine ─────────────────────

    @extend_schema(
        summary='Update task status — enforces state machine rules',
        tags=['Main Tasks'],
    )
    @audit_action(action='update', resource='MainTask')
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        task       = self.get_object()
        new_status = request.data.get('status')
        user       = request.user

        if not new_status:
            return Response(
                {'detail': 'status field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Department Head can only update tasks assigned to them
        if (user.role and user.role.name == 'department_head'
                and task.assigned_to != user):
            return Response(
                {'detail': 'You can only update status of tasks assigned to you.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_manager = (
            user.is_superuser or
            (user.role and user.role.name == 'it')
        )

        # Requirement 1 — validate transition via state machine
        valid, error = validate_transition(
            current_status=task.status,
            new_status=new_status,
            is_manager=is_manager,
        )

        if not valid:
            return Response(
                {'detail': error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = new_status
        task.save(update_fields=['status', 'updated_at'])

        return Response(
            MainTaskSerializer(task, context={'request': request}).data
        )

    # ── Attachments ───────────────────────────────────────────

    @extend_schema(
        request=TaskAttachmentSerializer,
        responses={201: TaskAttachmentSerializer(many=True)},
        summary='Upload files to a task',
        tags=['Main Tasks'],
    )
    @action(
        detail=True, methods=['post'], url_path='attachments',
        permission_classes=[IsAuthenticated, IsManager],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_attachments(self, request, pk=None):
        task  = self.get_object()
        files = request.FILES.getlist('files')

        if not files:
            return Response(
                {'detail': 'No files provided. Send files under the "files" key.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for f in files:
            attachment = TaskAttachment.objects.create(
                task=task,
                file=f,
                uploaded_by=request.user,
            )
            created.append(attachment)

        return Response(
            TaskAttachmentSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary='Delete a specific attachment from a task',
        tags=['Main Tasks'],
    )
    @action(
        detail=True, methods=['delete'],
        url_path='attachments/(?P<attachment_id>[^/.]+)',
        permission_classes=[IsAuthenticated, IsManager],
    )
    def delete_attachment(self, request, pk=None, attachment_id=None):
        task = self.get_object()
        try:
            attachment = TaskAttachment.objects.get(
                id=attachment_id, task=task
            )
        except TaskAttachment.DoesNotExist:
            return Response(
                {'detail': 'Attachment not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        attachment.file.delete(save=False)  # delete from storage
        attachment.delete()

        return Response(
            {'detail': 'Attachment deleted.'},
            status=status.HTTP_200_OK,
        )

    # ── My Tasks ──────────────────────────────────────────────

    @extend_schema(
        responses={200: MainTaskSerializer(many=True)},
        summary='Get tasks assigned to me',
        tags=['Main Tasks'],
    )
    @action(
        detail=False, methods=['get'], url_path='my-tasks',
        permission_classes=[IsAuthenticated],
    )
    def my_tasks(self, request):
        tasks = MainTask.objects.select_related(
            'created_by', 'assigned_to',
            'assigned_to__department', 'department',
        ).prefetch_related(
            'attachments', 'attachments__uploaded_by',
        ).filter(assigned_to=request.user)

        page = self.paginate_queryset(tasks)
        if page is not None:
            return self.get_paginated_response(
                MainTaskSerializer(page, many=True,
                                   context={'request': request}).data
            )
        return Response(
            MainTaskSerializer(tasks, many=True,
                               context={'request': request}).data
        )