# apps/tasks/serializers.py
from rest_framework import serializers
from apps.tasks.models    import MainTask, TaskAttachment , SubTask , Request
from apps.accounts.models import User, Role , Employee

class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = TaskAttachment
        fields = ['id', 'file', 'filename', 'uploaded_by', 'uploaded_at']
        read_only_fields = ['id', 'filename', 'uploaded_by', 'uploaded_at']


class AssignedToField(serializers.SlugRelatedField):
    """
    READ  : returns { id, full_name, department }
    WRITE : accepts a user ID, validates Department Head role
    """
    def to_representation(self, obj):
        return {
            'id'        : obj.id,
            'full_name' : obj.full_name,
            'department': obj.department.name if obj.department else None,
        }

    def to_internal_value(self, data):
        try:
            user = User.objects.select_related('role', 'department').get(pk=data)
        except (User.DoesNotExist, TypeError, ValueError):
            raise serializers.ValidationError('Invalid user ID.')

        if not user.role or user.role.name != Role.DEPARTMENT_HEAD:
            raise serializers.ValidationError(
                'Tasks can only be assigned to Department Heads.'
            )
        if not user.department:
            raise serializers.ValidationError(
                'This Department Head has no department assigned.'
            )
        return user


class MainTaskSerializer(serializers.ModelSerializer):
    created_by  = serializers.StringRelatedField(read_only=True)
    assigned_to = AssignedToField(
        slug_field='full_name',
        queryset=User.objects.select_related('role', 'department').filter(
            role__name=Role.DEPARTMENT_HEAD
        ),
        required=False,
        allow_null=True,
    )

    # Nested read — prefetch_related in ViewSet prevents N+1
    attachments = TaskAttachmentSerializer(many=True, read_only=True)

    # Write-only field for uploading multiple files in one request
    upload_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
    )

    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model  = MainTask
        fields = [
            'id', 'title', 'description', 'priority', 'status',
            'created_by', 'assigned_to', 'department',
            'start_date', 'due_date',
            'attachments', 'upload_files',
            'is_overdue', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_by', 'status',
            'created_at', 'updated_at',
        ]

    def get_is_overdue(self, obj):
        from django.utils import timezone
        if obj.due_date and obj.status != MainTask.Status.COMPLETED:
            return obj.due_date < timezone.now().date()
        return False

    def validate(self, data):
        start = data.get('start_date')
        due   = data.get('due_date')
        if start and due and due < start:
            raise serializers.ValidationError(
                'Due date cannot be before start date.'
            )
        return data

    def create(self, validated_data):
        files   = validated_data.pop('upload_files', [])
        task    = MainTask.objects.create(**validated_data)
        request = self.context.get('request')

        for f in files:
            TaskAttachment.objects.create(
                task=task,
                file=f,
                uploaded_by=request.user if request else None,
            )
        return task

    def update(self, instance, validated_data):
        files   = validated_data.pop('upload_files', [])
        request = self.context.get('request')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for f in files:
            TaskAttachment.objects.create(
                task=instance,
                file=f,
                uploaded_by=request.user if request else None,
            )
        return instance

class SubTaskAssignedToField(serializers.SlugRelatedField):
    """
    READ  : returns { id, full_name, email, department }
    WRITE : accepts an Employee ID
    """
    def to_representation(self, obj):
        return {
            'id'        : obj.id,
            'full_name' : obj.full_name,
            'email'     : obj.email,
            'department': obj.department.name if obj.department else None,
        }

    def to_internal_value(self, data):
        try:
            return Employee.objects.select_related('department').get(pk=data)
        except (Employee.DoesNotExist, TypeError, ValueError):
            raise serializers.ValidationError('Invalid employee ID.')


class SubTaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SubTask
        fields = [
            'id', 'title', 'description', 'notes',
            'estimated_hours', 'due_date',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        main_task = self.context.get('main_task')
        due       = data.get('due_date')
        if main_task and due and main_task.due_date and due > main_task.due_date:
            raise serializers.ValidationError(
                'SubTask due date cannot be after the MainTask due date.'
            )
        return data


class SubTaskAssignSerializer(serializers.ModelSerializer):
    assigned_to = SubTaskAssignedToField(
        slug_field='full_name',
        queryset=Employee.objects.select_related('department').filter(
            status='active'
        ),
        required=True,
    )

    class Meta:
        model  = SubTask
        fields = ['assigned_to']


class SubTaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SubTask
        fields = ['status', 'actual_hours', 'notes']

    def validate_status(self, value):
        if value == SubTask.Status.NOT_STARTED:
            instance = self.instance
            if instance and instance.status != SubTask.Status.NOT_STARTED:
                raise serializers.ValidationError(
                    'Cannot revert status back to not_started.'
                )
        return value


class SubTaskResponseSerializer(serializers.ModelSerializer):
    created_by  = serializers.StringRelatedField(read_only=True)
    assigned_to = SubTaskAssignedToField(
        slug_field='full_name',
        queryset=Employee.objects.all(),
        required=False,
        allow_null=True,
    )
    main_task_title = serializers.SerializerMethodField()
    is_overdue      = serializers.BooleanField(read_only=True)

    class Meta:
        model  = SubTask
        fields = [
            'id', 'title', 'description', 'notes', 'status',
            'main_task', 'main_task_title',
            'created_by', 'assigned_to',
            'estimated_hours', 'actual_hours',
            'due_date', 'is_overdue',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'main_task', 'created_by', 'created_at', 'updated_at']

    def get_main_task_title(self, obj):
        return obj.main_task.title


class RequestCreateSerializer(serializers.ModelSerializer):
    """
    Used by Employees to submit extension or exemption requests.
    """
    class Meta:
        model  = Request
        fields = [
            'id', 'request_type', 'subtask',
            'extension_days', 'reason',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        request_type   = data.get('request_type')
        extension_days = data.get('extension_days')

        # Extension requires extension_days
        if request_type == Request.RequestType.EXTENSION:
            if not extension_days or extension_days < 1:
                raise serializers.ValidationError(
                    'Extension requests require at least 1 extension day.'
                )

        # Exemption must not include extension_days
        if request_type == Request.RequestType.EXEMPTION and extension_days:
            raise serializers.ValidationError(
                'Exemption requests cannot include extension_days.'
            )

        # reason is mandatory — double check at serializer level
        if not data.get('reason', '').strip():
            raise serializers.ValidationError(
                'reason is required and cannot be blank.'
            )

        return data

    def validate_subtask(self, subtask):
        """
        Employee can only submit a request for a subtask assigned to them.
        Validated against the employee_id in the JWT token.
        """
        request = self.context.get('request')
        if not request:
            return subtask

        token = getattr(request, 'auth', None)
        if token and token.get('type') == 'employee':
            employee_id = token.get('employee_id')
            if not subtask.assigned_to or subtask.assigned_to.id != employee_id:
                raise serializers.ValidationError(
                    'You can only submit requests for subtasks assigned to you.'
                )

        # Cannot submit if already has a pending request of the same type
        request_type = self.initial_data.get('request_type')
        if request_type:
            existing = Request.objects.filter(
                subtask=subtask,
                employee_id=token.get('employee_id') if token else None,
                request_type=request_type,
                status=Request.Status.PENDING,
            ).exists()
            if existing:
                raise serializers.ValidationError(
                    f'You already have a pending {request_type} request for this subtask.'
                )

        return subtask


class RequestReviewSerializer(serializers.ModelSerializer):
    """
    Used by Department Heads to approve or reject a request.
    """
    class Meta:
        model  = Request
        fields = ['status', 'rejection_reason']

    def validate_status(self, value):
        if value not in [Request.Status.APPROVED, Request.Status.REJECTED]:
            raise serializers.ValidationError(
                'Status must be either approved or rejected.'
            )
        return value

    def validate(self, data):
        if data.get('status') == Request.Status.REJECTED:
            if not data.get('rejection_reason', '').strip():
                raise serializers.ValidationError(
                    'rejection_reason is required when rejecting a request.'
                )
        return data


class RequestResponseSerializer(serializers.ModelSerializer):
    subtask_title  = serializers.SerializerMethodField()
    employee_name  = serializers.SerializerMethodField()
    reviewed_by    = serializers.StringRelatedField(read_only=True)
    request_type   = serializers.CharField(source='get_request_type_display')
    status         = serializers.CharField(source='get_status_display')

    class Meta:
        model  = Request
        fields = [
            'id', 'request_type', 'status',
            'subtask', 'subtask_title',
            'employee', 'employee_name',
            'reviewed_by', 'extension_days',
            'reason', 'rejection_reason',
            'submitted_at', 'reviewed_at',
        ]
        read_only_fields = fields

    def get_subtask_title(self, obj):
        return obj.subtask.title

    def get_employee_name(self, obj):
        return obj.employee.full_name

# ─── Dashboard Serializers ────────────────────────────────────

class KPIManagerSerializer(serializers.Serializer):
    total_active_tasks = serializers.IntegerField()
    overall_progress   = serializers.FloatField()
    dept_efficiency    = serializers.FloatField()
    critical_delays    = serializers.IntegerField()


class PerformanceScorecardSerializer(serializers.Serializer):
    avg_completion_rate = serializers.FloatField()
    avg_delay_rate      = serializers.FloatField()
    quality_score       = serializers.FloatField()
    total_employees     = serializers.IntegerField()


class WarningEntrySerializer(serializers.Serializer):
    id              = serializers.IntegerField()
    full_name       = serializers.CharField()
    email           = serializers.EmailField()
    dept_name       = serializers.CharField(allow_null=True)
    delay_rate      = serializers.FloatField()
    completion_rate = serializers.FloatField()


class TopPerformerSerializer(serializers.Serializer):
    id               = serializers.IntegerField()
    full_name        = serializers.CharField()
    dept_name        = serializers.CharField(allow_null=True)
    completion_rate  = serializers.FloatField()
    delay_rate       = serializers.FloatField()
    performance_score = serializers.FloatField()


class LatestTaskSerializer(serializers.Serializer):
    id        = serializers.IntegerField()
    title     = serializers.CharField()
    priority  = serializers.CharField()
    status    = serializers.CharField()
    due_date  = serializers.DateField(allow_null=True)
    dept_name = serializers.CharField(allow_null=True)
    head_name = serializers.CharField(allow_null=True)


class ManagerDashboardSerializer(serializers.Serializer):
    kpi                   = KPIManagerSerializer()
    latest_tasks          = LatestTaskSerializer(many=True)
    performance_scorecard = PerformanceScorecardSerializer()
    warning_list          = WarningEntrySerializer(many=True)
    top_performers        = TopPerformerSerializer(many=True)


# ── Employee Dashboard ────────────────────────────────────────

class KPIEmployeeSerializer(serializers.Serializer):
    assigned_tasks       = serializers.IntegerField()
    in_progress          = serializers.IntegerField()
    completed_this_month = serializers.IntegerField()
    pending_requests     = serializers.IntegerField()


class UpcomingDeadlineSerializer(serializers.Serializer):
    id              = serializers.IntegerField()
    title           = serializers.CharField()
    main_task_title = serializers.CharField()
    dept_name       = serializers.CharField(allow_null=True)
    due_date        = serializers.DateField()
    status          = serializers.CharField()


class VelocityEntrySerializer(serializers.Serializer):
    day       = serializers.CharField()
    date      = serializers.CharField()
    completed = serializers.IntegerField()


class EmployeeDashboardSerializer(serializers.Serializer):
    kpi                = KPIEmployeeSerializer()
    upcoming_deadlines = UpcomingDeadlineSerializer(many=True)
    velocity           = VelocityEntrySerializer(many=True)
    priority_mix       = serializers.DictField(child=serializers.FloatField())


# ── Employee Performance Directory ────────────────────────────

class PerformanceSummarySerializer(serializers.Serializer):
    total_staff      = serializers.IntegerField()
    avg_performance  = serializers.FloatField()
    avg_delay_rate   = serializers.FloatField()
    compliance_rate  = serializers.FloatField()
    critical_delays  = serializers.IntegerField()


class EmployeePerformanceSerializer(serializers.Serializer):
    id                = serializers.IntegerField()
    full_name         = serializers.CharField()
    email             = serializers.EmailField()
    dept_name         = serializers.CharField(allow_null=True)
    status            = serializers.CharField()
    total_sub         = serializers.IntegerField()
    completion_rate   = serializers.FloatField()
    delay_rate        = serializers.FloatField()
    performance_score = serializers.FloatField()
    performance_label = serializers.CharField()


class EmployeeDirectorySerializer(serializers.Serializer):
    summary   = PerformanceSummarySerializer()
    employees = EmployeePerformanceSerializer(many=True)


class WarningListSerializer(serializers.Serializer):
    
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    dept_name = serializers.CharField(allow_null=True)
    delay_rate = serializers.FloatField()
    completion_rate = serializers.FloatField()
    performance_score = serializers.FloatField()
    performance_label = serializers.CharField()
    last_activity = serializers.DateTimeField(allow_null=True, required=False)


class DepartmentWorkloadSerializer(serializers.Serializer):

    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    active_subtasks_count = serializers.IntegerField()
    overdue_subtasks_count = serializers.IntegerField(required=False)