# apps/tasks/views.py
import os
from rest_framework             import status, viewsets, mixins
from rest_framework.decorators  import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response    import Response
from rest_framework.parsers     import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions  import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils      import extend_schema
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from apps.tasks.models         import MainTask, TaskAttachment, Request, SubTask
from apps.tasks.serializers    import MainTaskSerializer, TaskAttachmentSerializer
from apps.accounts.permissions import IsManager, IsDepartmentHead
from apps.accounts.audit       import audit_action
from apps.tasks.serializers import (
    MainTaskSerializer, TaskAttachmentSerializer,
    SubTaskCreateSerializer, SubTaskAssignSerializer,
    SubTaskStatusSerializer, SubTaskResponseSerializer,
    RequestCreateSerializer, RequestReviewSerializer,
    RequestResponseSerializer,
)
from apps.tasks.state_machine  import validate_transition, validate_subtask_transition
from apps.accounts.models      import Employee
from django.utils import timezone       
from datetime     import timedelta, date
from apps.tasks.selectors    import get_manager_dashboard, invalidate_dashboard_cache
from apps.tasks.serializers  import ManagerDashboardSerializer


# Security constants for file uploads
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.xlsx', '.xls', '.txt', '.zip']
ALLOWED_MIME_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'application/zip',
    'application/x-zip-compressed',
]


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
        response = super().create(request, *args, **kwargs)
        invalidate_dashboard_cache()  # Clear cache on data change
        return response

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
        response = super().update(request, *args, **kwargs)
        invalidate_dashboard_cache()  # Clear cache on data change
        return response

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a main task',
        tags=['Main Tasks'],
    )
    @audit_action(action='delete', resource='MainTask')
    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        invalidate_dashboard_cache()  # Clear cache on data change
        return response

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
        
        invalidate_dashboard_cache()  # Clear cache
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
        invalidate_dashboard_cache()  # Clear cache on status change

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
        
        # SECURITY: Validate file count, size, and type
        if len(files) > 10:
            return Response(
                {'detail': 'Maximum 10 files allowed per upload.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        errors = []

        for f in files:
            # Validate file size
            if f.size > MAX_FILE_SIZE:
                errors.append(f"{f.name}: File size exceeds 10MB limit")
                continue
            
            # Validate extension
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append(f"{f.name}: File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
                continue
            
            # Validate MIME type (basic)
            if f.content_type not in ALLOWED_MIME_TYPES:
                errors.append(f"{f.name}: Invalid MIME type {f.content_type}")
                continue
            
            try:
                attachment = TaskAttachment.objects.create(
                    task=task,
                    file=f,
                    uploaded_by=request.user,
                )
                created.append(attachment)
            except Exception as e:
                errors.append(f"{f.name}: Upload failed - {str(e)}")

        response_data = {
            'created': TaskAttachmentSerializer(created, many=True).data,
            'count': len(created)
        }
        if errors:
            response_data['errors'] = errors
            
        status_code = status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)

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

    # ── Reports / Stats ───────────────────────────────────────

    @extend_schema(
        summary='Aggregate task statistics for the reports dashboard',
        tags=['Main Tasks'],
    )
    @action(
        detail=False, methods=['get'], url_path='stats',
        permission_classes=[IsAuthenticated],
    )
    def stats(self, request):
        from django.utils import timezone
        from django.db.models import Q
        from datetime import timedelta, date

        today = timezone.now().date()
        active_statuses = ['unassigned', 'assigned', 'in_progress']

        # ── KPIs ──────────────────────────────────────────────
        total     = MainTask.objects.count()
        completed = MainTask.objects.filter(status='completed').count()
        success_rate = round((completed / total * 100) if total > 0 else 0, 1)

        overdue_qs = MainTask.objects.filter(
            due_date__lt=today,
            status__in=active_statuses,
        )
        delay_days = [
            (today - t.due_date).days
            for t in overdue_qs
            if t.due_date
        ]
        avg_delay = round(sum(delay_days) / len(delay_days), 1) if delay_days else 0.0

        # ── Monthly completion trend (last 6 months) ──────────
        monthly_trend = []
        for i in range(5, -1, -1):
            # compute month start by going back i months from today
            m = today.month - i
            y = today.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            month_start = date(y, m, 1)
            if m == 12:
                month_end = date(y + 1, 1, 1)
            else:
                month_end = date(y, m + 1, 1)

            count = MainTask.objects.filter(
                status='completed',
                updated_at__date__gte=month_start,
                updated_at__date__lt=month_end,
            ).count()
            monthly_trend.append({
                'month': month_start.strftime('%b'),
                'completed': count,
            })

        # ── Critical tasks (due ≤ 7 days OR overdue, high/urgent) ──
        critical_qs = MainTask.objects.filter(
            Q(due_date__lte=today + timedelta(days=7)),
            status__in=active_statuses,
            priority__in=['high', 'urgent'],
        ).order_by('due_date')[:5]

        critical_tasks = []
        for t in critical_qs:
            days = (t.due_date - today).days if t.due_date else None
            critical_tasks.append({
                'id':           t.id,
                'title':        t.title,
                'priority':     t.priority,
                'due_date':     t.due_date,
                'days_until_due': days,
                'is_overdue':   (t.due_date < today) if t.due_date else False,
            })

        # ── Active milestones (assigned/in_progress with dept) ──
        milestones_qs = MainTask.objects.select_related(
            'department', 'assigned_to',
        ).prefetch_related('subtasks').filter(
            status__in=['assigned', 'in_progress'],
        ).order_by('due_date')[:6]

        milestones = []
        for t in milestones_qs:
            sub_total    = t.subtasks.count()
            sub_done     = t.subtasks.filter(status='completed').count()
            progress     = round((sub_done / sub_total * 100) if sub_total > 0 else 0)

            if t.due_date:
                days_left = (t.due_date - today).days
                if days_left < 0:
                    task_status = 'delayed'
                elif days_left <= 3:
                    task_status = 'at-risk'
                else:
                    task_status = 'on-track'
            else:
                task_status = 'on-track'

            milestones.append({
                'id':        t.id,
                'title':     t.title,
                'dept':      t.department.name if t.department else 'Unassigned',
                'due_date':  t.due_date.strftime('%b %d') if t.due_date else '—',
                'progress':  progress,
                'status':    task_status,
            })

        return Response({
            'kpi': {
                'total_tasks':     total,
                'completed_tasks': completed,
                'success_rate':    success_rate,
                'avg_delay_days':  avg_delay,
            },
            'monthly_trend':  monthly_trend,
            'critical_tasks': critical_tasks,
            'milestones':     milestones,
        })
    
    @extend_schema(
        summary='Manager dashboard statistics',
        tags=['Main Tasks'],
    )
    @action(
        detail=False, methods=['get'], url_path='dashboard',
        permission_classes=[IsAuthenticated, IsManager],
    )
    def dashboard(self, request):
        data       = get_manager_dashboard()
        serializer = ManagerDashboardSerializer(data)
        return Response(serializer.data)


class SubTaskViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    SubTasks are always accessed under a MainTask:
        /api/tasks/main-tasks/{main_task_pk}/subtasks/

    Permissions:
      - List / Retrieve   : Authenticated
      - Create            : Department Head (of the assigned MainTask)
      - Update / Delete   : Department Head
      - assign action     : Department Head
      - update_status     : Employee (their own subtask) or Dept Head
    """
    serializer_class = SubTaskResponseSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['status']

    def _get_main_task(self):
        return get_object_or_404(
            MainTask.objects.select_related('assigned_to', 'department'),
            pk=self.kwargs['main_task_pk'],
        )

    def get_queryset(self):
        return SubTask.objects.select_related(
            'main_task', 'created_by',
            'assigned_to', 'assigned_to__department',
        ).filter(main_task_id=self.kwargs['main_task_pk'])

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        if self.action == 'update_status':
            return [IsAuthenticated()]   # object-level check inside action
        return [IsAuthenticated(), IsDepartmentHead()]

    # ── CRUD ──────────────────────────────────────────────────

    @extend_schema(
        request=SubTaskCreateSerializer,
        responses={201: SubTaskResponseSerializer},
        summary='Create a subtask under a main task',
        tags=['SubTasks'],
    )
    @audit_action(action='create', resource='SubTask')
    def create(self, request, *args, **kwargs):
        main_task = self._get_main_task()

        # Only the Department Head assigned to this MainTask can create subtasks
        if main_task.assigned_to != request.user:
            return Response(
                {'detail': 'Only the assigned Department Head can create subtasks.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SubTaskCreateSerializer(
            data=request.data,
            context={'request': request, 'main_task': main_task},
        )
        serializer.is_valid(raise_exception=True)
        subtask = serializer.save(
            main_task=main_task,
            created_by=request.user,
            status=SubTask.Status.NOT_STARTED,
        )
        
        invalidate_dashboard_cache()  # Clear cache
        return Response(
            SubTaskResponseSerializer(subtask).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: SubTaskResponseSerializer(many=True)},
        summary='List subtasks for a main task',
        tags=['SubTasks'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={200: SubTaskResponseSerializer},
        summary='Get a subtask',
        tags=['SubTasks'],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=SubTaskCreateSerializer,
        responses={200: SubTaskResponseSerializer},
        summary='Update a subtask',
        tags=['SubTasks'],
    )
    @audit_action(action='update', resource='SubTask')
    def update(self, request, *args, **kwargs):
        subtask    = self.get_object()
        serializer = SubTaskCreateSerializer(
            subtask,
            data=request.data,
            partial=True,
            context={'request': request, 'main_task': subtask.main_task},
        )
        serializer.is_valid(raise_exception=True)
        subtask = serializer.save()
        invalidate_dashboard_cache()  # Clear cache
        return Response(SubTaskResponseSerializer(subtask).data)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a subtask',
        tags=['SubTasks'],
    )
    @audit_action(action='delete', resource='SubTask')
    def destroy(self, request, *args, **kwargs):
        subtask = self.get_object()
        subtask.delete()
        invalidate_dashboard_cache()  # Clear cache
        return Response(
            {'detail': 'SubTask deleted successfully.'},
            status=status.HTTP_200_OK,
        )

    # ── Assign ────────────────────────────────────────────────

    @extend_schema(
        request=SubTaskAssignSerializer,
        responses={200: SubTaskResponseSerializer},
        summary='Assign subtask to an Employee',
        tags=['SubTasks'],
    )
    @audit_action(action='update', resource='SubTask')
    @action(
        detail=True, methods=['patch'], url_path='assign',
        permission_classes=[IsAuthenticated, IsDepartmentHead],
    )
    def assign(self, request, **kwargs):
        subtask    = self.get_object()
        main_task  = self._get_main_task()

        if main_task.assigned_to != request.user:
            return Response(
                {'detail': 'Only the assigned Department Head can assign subtasks.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SubTaskAssignSerializer(
            subtask, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        employee = serializer.validated_data.get('assigned_to')

        # Validate employee belongs to the same department
        if employee.department != main_task.department:
            return Response(
                {
                    'detail': (
                        f'{employee.full_name} does not belong to '
                        f'{main_task.department} department.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(status=SubTask.Status.IN_PROGRESS)
        invalidate_dashboard_cache()  # Clear cache
        subtask.refresh_from_db()

        return Response(SubTaskResponseSerializer(subtask).data)

    # ── Status Update with State Machine ─────────────────────

    @extend_schema(
        request=SubTaskStatusSerializer,
        responses={200: SubTaskResponseSerializer},
        summary='Update subtask status — enforces state machine rules',
        tags=['SubTasks'],
    )
    @audit_action(action='update', resource='SubTask')
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, **kwargs):
        subtask    = self.get_object()
        new_status = request.data.get('status')
        user       = request.user

        if not new_status:
            return Response(
                {'detail': 'status field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_head     = user.role and user.role.name == 'department_head'
        is_manager  = user.is_superuser or (user.role and user.role.name == 'it')

        # Employee can only update their own subtask
        if not is_head and not is_manager:
            if subtask.assigned_to is None or subtask.assigned_to.id != user.id:
                return Response(
                    {'detail': 'You can only update subtasks assigned to you.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Department Head can only update subtasks under their MainTask
        if is_head:
            main_task = self._get_main_task()
            if main_task.assigned_to != user:
                return Response(
                    {'detail': 'You can only update subtasks in your assigned tasks.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        valid, error = validate_subtask_transition(
            current_status=subtask.status,
            new_status=new_status,
            is_head=is_head or is_manager,
        )

        if not valid:
            return Response(
                {'detail': error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save optional fields alongside status
        serializer = SubTaskStatusSerializer(
            subtask, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_dashboard_cache()  # Clear cache

        subtask.refresh_from_db()
        return Response(SubTaskResponseSerializer(subtask).data)

    # ── My SubTasks (Employee view) ───────────────────────────

    @extend_schema(
        responses={200: SubTaskResponseSerializer(many=True)},
        summary='Get subtasks assigned to me (Employee)',
        tags=['SubTasks'],
    )
    @action(
        detail=False, methods=['get'], url_path='my-subtasks',
        permission_classes=[IsAuthenticated],
    )
    def my_subtasks(self, request):
        """
        Returns subtasks assigned to the currently logged-in Employee.
        Reads employee_id from the JWT token payload.
        """
        token = request.auth
        if not token or token.get('type') != 'employee':
            return Response(
                {'detail': 'This endpoint is for employees only.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee_id = token.get('employee_id')
        subtasks = SubTask.objects.select_related(
            'main_task', 'created_by',
            'assigned_to', 'assigned_to__department',
        ).filter(assigned_to_id=employee_id)

        page = self.paginate_queryset(subtasks)
        if page is not None:
            return self.get_paginated_response(
                SubTaskResponseSerializer(page, many=True).data
            )
        return Response(SubTaskResponseSerializer(subtasks, many=True).data)
    
    @extend_schema(
        summary='Employee personal dashboard statistics',
        tags=['SubTasks'],
    )
    @action(
        detail=False, methods=['get'], url_path='employee-dashboard',
        permission_classes=[IsAuthenticated],
    )
    def employee_dashboard(self, request):
        from apps.tasks.selectors   import get_employee_dashboard
        from apps.tasks.serializers import EmployeeDashboardSerializer

        token = request.auth
        if not token or token.get('type') != 'employee':
            return Response(
                {'detail': 'This endpoint is for employees only.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        data       = get_employee_dashboard(employee_id=token.get('employee_id'))
        serializer = EmployeeDashboardSerializer(data)
        return Response(serializer.data)




class RequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Handles Extension and Exemption requests submitted by Employees
    and reviewed by Department Heads.

    Permissions:
      - Create          : Employee (via JWT employee token)
      - List / Retrieve : Authenticated
      - review action   : Department Head
      - my_requests     : Employee
      - pending         : Department Head
    """
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['status', 'request_type', 'subtask']

    def get_serializer_class(self):
        if self.action == 'create':
            return RequestCreateSerializer
        if self.action == 'review':
            return RequestReviewSerializer
        return RequestResponseSerializer

    def get_queryset(self):
        return Request.objects.select_related(
            'subtask', 'subtask__main_task',
            'employee', 'reviewed_by',
        ).all()

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]   # employee check is inside the view
        if self.action == 'review':
            return [IsAuthenticated(), IsDepartmentHead()]
        return [IsAuthenticated()]

    # ── Create (Employee only) ────────────────────────────────

    @extend_schema(
        request=RequestCreateSerializer,
        responses={201: RequestResponseSerializer},
        summary='Submit an extension or exemption request',
        tags=['Requests'],
    )
    def create(self, request, *args, **kwargs):
        # Only employees can submit requests
        token = request.auth
        if not token or token.get('type') != 'employee':
            return Response(
                {'detail': 'Only employees can submit requests.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee_id = token.get('employee_id')
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RequestCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        req = serializer.save(
            employee=employee,
            status=Request.Status.PENDING,
        )

        return Response(
            RequestResponseSerializer(req).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: RequestResponseSerializer(many=True)},
        summary='List all requests',
        tags=['Requests'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={200: RequestResponseSerializer},
        summary='Get a request',
        tags=['Requests'],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # ── Review (Department Head only) ─────────────────────────

    @extend_schema(
        request=RequestReviewSerializer,
        responses={200: RequestResponseSerializer},
        summary='Approve or reject a request',
        tags=['Requests'],
    )
    @audit_action(action='update', resource='Request')
    @action(
        detail=True, methods=['patch'], url_path='review',
        permission_classes=[IsAuthenticated, IsDepartmentHead],
    )
    def review(self, request, pk=None):
        from django.utils import timezone

        req = self.get_object()

        # Can only review pending requests
        if req.status != Request.Status.PENDING:
            return Response(
                {'detail': f'This request has already been {req.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Department Head can only review requests for their subtasks
        subtask_head = req.subtask.main_task.assigned_to
        if subtask_head != request.user:
            return Response(
                {'detail': 'You can only review requests for subtasks in your assigned tasks.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RequestReviewSerializer(req, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']

        # If approved extension request — extend the subtask due date
        if (new_status == Request.Status.APPROVED
                and req.request_type == Request.RequestType.EXTENSION
                and req.extension_days):
            from datetime import timedelta
            subtask = req.subtask
            if subtask.due_date:
                subtask.due_date = subtask.due_date + timedelta(days=req.extension_days)
                subtask.save(update_fields=['due_date', 'updated_at'])

        # If approved exemption — unassign employee from the subtask
        if (new_status == Request.Status.APPROVED
                and req.request_type == Request.RequestType.EXEMPTION):
            req.subtask.assigned_to = None
            req.subtask.status      = SubTask.Status.NOT_STARTED
            req.subtask.save(update_fields=['assigned_to', 'status', 'updated_at'])

        serializer.save(
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        
        invalidate_dashboard_cache()  # Clear cache as task data changed

        req.refresh_from_db()
        return Response(RequestResponseSerializer(req).data)

    # ── My Requests (Employee) ────────────────────────────────

    @extend_schema(
        responses={200: RequestResponseSerializer(many=True)},
        summary='Get my submitted requests (Employee)',
        tags=['Requests'],
    )
    @action(
        detail=False, methods=['get'], url_path='my-requests',
        permission_classes=[IsAuthenticated],
    )
    def my_requests(self, request):
        token = request.auth
        if not token or token.get('type') != 'employee':
            return Response(
                {'detail': 'This endpoint is for employees only.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee_id = token.get('employee_id')
        requests = Request.objects.select_related(
            'subtask', 'subtask__main_task', 'employee', 'reviewed_by',
        ).filter(employee_id=employee_id).order_by('-submitted_at')

        page = self.paginate_queryset(requests)
        if page is not None:
            return self.get_paginated_response(
                RequestResponseSerializer(page, many=True).data
            )
        return Response(RequestResponseSerializer(requests, many=True).data)

    # ── Pending requests (Department Head) ────────────────────

    @extend_schema(
        responses={200: RequestResponseSerializer(many=True)},
        summary='Get pending requests for my subtasks (Department Head)',
        tags=['Requests'],
    )
    @action(
        detail=False, methods=['get'], url_path='pending',
        permission_classes=[IsAuthenticated, IsDepartmentHead],
    )
    def pending(self, request):
        """
        Returns all PENDING requests for subtasks under MainTasks
        assigned to the current Department Head.
        """
        requests = Request.objects.select_related(
            'subtask', 'subtask__main_task', 'employee', 'reviewed_by',
        ).filter(
            status=Request.Status.PENDING,
            subtask__main_task__assigned_to=request.user,
        ).order_by('-submitted_at')

        page = self.paginate_queryset(requests)
        if page is not None:
            return self.get_paginated_response(
                RequestResponseSerializer(page, many=True).data
            )
        return Response(RequestResponseSerializer(requests, many=True).data)